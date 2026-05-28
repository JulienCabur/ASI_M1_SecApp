"""Login médecin par certificat (gate avant le flow OIDC standard).

Distinct de `/auth/challenge` (utilisé par le reset) pour éviter qu'une preuve
produite pour un reset puisse être rejouée pour ouvrir une session, et inversement.
"""

import json
import secrets
import time
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.database import get_db
from core.oidc import build_authorize_url, generate_pkce_pair
from core.session import set_oidc_state_cookie
from schema.auth_schema import (
    CertLoginProofRequest,
    CertificateRequest,
    CertLoginProofResponse,
    ChallengeResponse,
)
from service.auth_service import AuthService, DoctorConflictError
from service.log_service import LogsService
from service.file_service import FileService
from schema.device_schema import JWKSchema


router = APIRouter()
logs_service = LogsService("backend_auth")


@router.get("/cert/login/challenge", response_model=ChallengeResponse)
async def cert_login_challenge_route(
    username: str = Query(..., description="Username (CN du certificat médecin)"),
    db: Session = Depends(get_db),
) -> ChallengeResponse:
    auth_service = AuthService(db=db)
    try:
        return auth_service.generate_challenge(username)
    except Exception:
        # Réponse non-distinguable pour empêcher l'énumération de comptes.
        # On renvoie un nonce/timestamp factices ; la vérification échouera
        # de toute façon faute de challenge en DB.
        return ChallengeResponse(nonce="0" * 32, timestamp="1970-01-01T00:00:00.000Z")


@router.post("/cert/login/proof", response_model=CertLoginProofResponse)
async def cert_login_proof_route(
    body: CertLoginProofRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Vérifie la preuve de possession du certificat et prépare le redirect OIDC.

    En cas de succès, on dépose `secuapp_oidc_state` (incluant `cert_proven_username`)
    et on renvoie l'`authorize_url` Keycloak. Le front fait `window.location = url`."""
    auth_service = AuthService(db=db)
    client_ip = request.client.host if request.client else "unknown"
    try:
        auth_service.verify_challenge_response(
            username=body.username,
            nonce=body.nonce,
            timestamp=body.timestamp,
            signature=body.signature,
            certificate=body.certificate,
        )
    except Exception as e:
        auth_service.clear_challenge(username=body.username)
        await logs_service.add_logs(
            action=f"CERT_LOGIN_PROOF_FAIL:{client_ip}",
            log_level="WARNING",
            user_id=body.username,
            user_role="doctor",
            patient_id="null",
            message=str(e),
        )
        # Message générique côté client : on ne précise pas si c'est nonce, timestamp,
        # CN ou signature qui a échoué (anti oracle).
        raise HTTPException(status_code=400, detail="Vérification du certificat échouée")

    state = secrets.token_urlsafe(32)
    verifier, challenge = generate_pkce_pair()
    # `prompt=login` : empêche Keycloak d'auto-login avec un compte précédent
    # (cookie KEYCLOAK_IDENTITY toujours vivant). Indispensable quand on change
    # de médecin dans la même session navigateur via .p12.
    # `login_hint` : pré-remplit le champ username Keycloak avec le CN du cert
    # qu'on vient de prouver, pour éviter une saisie en double.
    authorize_url = build_authorize_url(
        state=state,
        code_challenge=challenge,
        force_reauth=True,
        login_hint=body.username,
    )

    redirect_to = body.redirect_to if body.redirect_to.startswith("/") else "/"

    response = JSONResponse({"authorize_url": authorize_url})
    set_oidc_state_cookie(
        response,
        {
            "state": state,
            "code_verifier": verifier,
            "redirect_to": redirect_to,
            "cert_proven_username": body.username,
        },
    )
    await logs_service.add_logs(
        action="CERT_LOGIN_PROOF_OK",
        log_level="INFO",
        user_id=body.username,
        user_role="doctor",
        patient_id="null",
    )
    return response

@router.post("/register_doctor", response_model=Dict[str, Any])
async def register_doctor_route(
    user_info: CertificateRequest = Form(...),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    auth_service = AuthService(db=db)
    file_service = FileService(db=db, storage_path="./cert_storage")
    try:
        # Pré-vérification d'unicité avant d'émettre un certificat PKI : un doublon
        # détecté ici évite une révocation derrière. La création Keycloak revérifie
        # de toute façon (course possible entre deux requêtes simultanées).
        auth_service.check_doctor_uniqueness(user_info.username, user_info.email)
        auth_service.generate_csr(user_info.username, user_info.organization)
        await logs_service.add_logs(action="GENERATE_CSR", log_level="INFO", user_id=user_info.username, user_role="doctor", patient_id="null")
        time.sleep(5)
        cert_path = auth_service.check_csr_signed(user_info.username)
        await logs_service.add_logs(action="CHECK_CSR_SIGNED", log_level="INFO", user_id=user_info.username, user_role="doctor", patient_id="null")
        p12_password = auth_service.create_doctor_in_keycloak(cert_path, user_info)
        await logs_service.add_logs(action="REGISTER_DOCTOR", log_level="INFO", user_id=user_info.username, user_role="doctor", patient_id="null")
        p12_content = file_service.get_base64_file_content(cert_path)
        await logs_service.add_logs(action="GET_P12_CONTENT", log_level="INFO", user_id=user_info.username, user_role="doctor", patient_id="null")
        auth_service.delete_sensitive_files(user_info.username)
        await logs_service.add_logs(action="DELETE_SENSITIVE_FILES", log_level="INFO", user_id=user_info.username, user_role="doctor", patient_id="null")
        return {
            "status": "success",
            "username": user_info.username,
            "certificate_b64": p12_content,
            "password": p12_password,
            "filename": f"{user_info.username}.p12",
        }
    except DoctorConflictError as e:
        # 409 ciblé : la couche présentation préserve `field` pour que le front
        # surligne le bon input (username ou email) sans parser un message libre.
        raise HTTPException(
            status_code=409,
            detail={"message": str(e), "field": e.field},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'enregistrement du médecin: {str(e)}")

@router.post("/store_public_mek")
async def store_public_mek_route(
    public_mek_jwk: str = Form(..., description="JWK sérialisée en JSON"),
    doctor_id: str = Form(...),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Stocke la public MEK d'un médecin (JWK RSA-OAEP).

    Le front envoie tout en `application/x-www-form-urlencoded` ; FastAPI ne
    permet pas de mélanger Form(...) et un body Pydantic, donc on reçoit la
    JWK en chaîne JSON et on la valide ici via `JWKSchema`.
    """
    try:
        jwk_dict = json.loads(public_mek_jwk)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="public_mek_jwk doit être un JSON valide")
    try:
        validated = JWKSchema.model_validate(jwk_dict)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"JWK invalide : {e}")

    auth_service = AuthService(db=db)
    try:
        auth_service.store_public_mek(doctor_id, validated.model_dump(exclude_none=True))
        return {"status": "Public MEK stored successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error storing public MEK: {str(e)}")
