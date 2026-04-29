"""Login médecin par certificat (gate avant le flow OIDC standard).

Distinct de `/auth/challenge` (utilisé par le reset) pour éviter qu'une preuve
produite pour un reset puisse être rejouée pour ouvrir une session, et inversement.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.database import get_db
from core.oidc import build_authorize_url, generate_pkce_pair
from core.session import set_oidc_state_cookie
from schema.auth_schema import (
    CertLoginProofRequest,
    CertLoginProofResponse,
    ChallengeResponse,
)
from service.auth_service import AuthService
from service.log_service import LogsService

router = APIRouter()
logs_service = LogsService()


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
    except Exception:
        auth_service.clear_challenge(username=body.username)
        logs_service.add_logs(
            action=f"CERT_LOGIN_PROOF_FAIL:{client_ip}",
            log_level="WARNING",
            user_id=body.username,
            user_role="doctor",
            patient_id="null",
        )
        # Message générique côté client : on ne précise pas si c'est nonce, timestamp,
        # CN ou signature qui a échoué (anti oracle).
        raise HTTPException(status_code=400, detail="Vérification du certificat échouée")

    state = secrets.token_urlsafe(32)
    verifier, challenge = generate_pkce_pair()
    authorize_url = build_authorize_url(state=state, code_challenge=challenge)

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
    logs_service.add_logs(
        action="CERT_LOGIN_PROOF_OK",
        log_level="INFO",
        user_id=body.username,
        user_role="doctor",
        patient_id="null",
    )
    return response
