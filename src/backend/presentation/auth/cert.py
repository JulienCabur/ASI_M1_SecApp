"""Login médecin par certificat (gate avant le flow OIDC standard).

Distinct de `/auth/challenge` (utilisé par le reset) pour éviter qu'une preuve
produite pour un reset puisse être rejouée pour ouvrir une session, et inversement.
"""

import json
import os
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
        raise HTTPException(status_code=400, detail="Vérification du certificat échouée")

    state = secrets.token_urlsafe(32)
    verifier, challenge = generate_pkce_pair()
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
            "flow_type": body.flow_type,
        },
    )
    await logs_service.add_logs(
        action="CERT_LOGIN_PROOF_OK",
        log_level="INFO",
        user_id=body.username,
        user_role="doctor",
        patient_id="null",
        message="Certificate login proof verified successfully",
    )
    return response

_PKI_SIGN_POLL_INTERVAL = float(os.getenv("PKI_SIGN_POLL_INTERVAL", "0.5"))
_PKI_SIGN_TIMEOUT = float(os.getenv("PKI_SIGN_TIMEOUT", "30"))


@router.post("/register_doctor", response_model=Dict[str, Any])
async def register_doctor_route(
    user_info: CertificateRequest = Form(...),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Émet un certificat médecin à partir d'un CSR généré dans le navigateur.

    Le navigateur produit la paire de clés RSA et le CSR ; le serveur valide
    strictement le subject, fait signer par la PKI, crée le compte Keycloak
    (en stockant le serial), puis renvoie le certificat PEM signé + la chaîne
    CA. Le .p12 est assemblé côté navigateur (la clé privée n'a jamais quitté
    le client).
    """
    auth_service = AuthService(db=db)
    try:
        auth_service.check_doctor_uniqueness(user_info.username, user_info.email)
        auth_service.submit_browser_csr(
            csr_pem=user_info.csr,
            common_name=user_info.username,
            organization=user_info.organization,
        )
        await logs_service.add_logs(action="SUBMIT_CSR", log_level="INFO", user_id=user_info.username, user_role="doctor", patient_id="null", message="CSR submitted for doctor registration")
        deadline = time.monotonic() + _PKI_SIGN_TIMEOUT
        cert_path = None
        while time.monotonic() < deadline:
            try:
                cert_path = auth_service.check_csr_signed(user_info.username)
                break
            except Exception:
                time.sleep(_PKI_SIGN_POLL_INTERVAL)
        if cert_path is None:
            auth_service.delete_sensitive_files(user_info.username)
            raise HTTPException(status_code=504, detail="La PKI n'a pas signé le CSR dans le délai imparti")
        await logs_service.add_logs(action="CHECK_CSR_SIGNED", log_level="INFO", user_id=user_info.username, user_role="roles_doctor", patient_id="null", message="CSR verified as signed")

        cert_pem = auth_service.create_doctor_in_keycloak(cert_path, user_info)
        await logs_service.add_logs(action="REGISTER_DOCTOR", log_level="INFO", user_id=user_info.username, user_role="roles_doctor", patient_id="null", message="Doctor registered successfully")

        ca_chain_pem = auth_service.read_ca_chain_pem()

        auth_service.delete_sensitive_files(user_info.username)
        await logs_service.add_logs(action="DELETE_SENSITIVE_FILES", log_level="INFO", user_id=user_info.username, user_role="roles_doctor", patient_id="null", message="Sensitive files deleted after registration")
        return {
            "status": "success",
            "username": user_info.username,
            "certificate_pem": cert_pem,
            "ca_chain_pem": ca_chain_pem,
        }
    except DoctorConflictError as e:
        raise HTTPException(status_code=409,detail={"message": str(e), "field": e.field})
    except HTTPException:
        raise
    except Exception as e:
        try:
            await logs_service.add_logs(action="DELETE_SENSITIVE_FILES", log_level="INFO", user_id=user_info.username, user_role="roles_doctor", patient_id="null", message="Sensitive files deleted after registration")
            auth_service.delete_sensitive_files(user_info.username)
        except Exception:
            pass
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
        await logs_service.add_logs(action="STORE_PUBLIC_MEK_RECEIVED", log_level="INFO", user_id=doctor_id, user_role="roles_doctor", patient_id="null", message="Received request to store public MEK")
    except json.JSONDecodeError:
        await logs_service.add_logs(action="STORE_PUBLIC_MEK_INVALID_JSON", log_level="WARNING", user_id=doctor_id, user_role="roles_doctor", patient_id="null", message="Invalid JSON for public MEK JWK")
        raise HTTPException(status_code=422, detail="public_mek_jwk doit être un JSON valide")
    try:
        validated = JWKSchema.model_validate(jwk_dict)
    except Exception as e:
        await logs_service.add_logs(action="STORE_PUBLIC_MEK_INVALID_JWK", log_level="WARNING", user_id=doctor_id, user_role="roles_doctor", patient_id="null", message=f"Invalid JWK: {e}")
        raise HTTPException(status_code=422, detail=f"JWK invalide : {e}")

    auth_service = AuthService(db=db)
    try:
        auth_service.store_public_mek(doctor_id, validated.model_dump(exclude_none=True))
        return {"status": "Public MEK stored successfully"}
    except Exception as e:
        await logs_service.add_logs(action="STORE_PUBLIC_MEK_ERROR", log_level="WARNING", user_id=doctor_id, user_role="roles_doctor", patient_id="null", message=f"Error storing public MEK: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error storing public MEK: {str(e)}")
