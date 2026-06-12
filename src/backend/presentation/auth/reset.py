"""Reset des credentials : par mail (patient) ou par certificat (médecin)."""

import time
import traceback
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from core.database import get_db
from schema.auth_schema import ChallengeResponseRequest, PasswordResetRequest
from service.auth_service import AuthService
from service.log_service import LogsService

router = APIRouter()
logs_service = LogsService("backend_auth")

# Rate-limit in memory (process-local). Move to Redis for multi-worker deployments.
_RESET_RATE_LIMIT: Dict[str, list] = {}
_ADD_DEVICE_RATE_LIMIT: Dict[str, list] = {}


def _check_rate_limit(store: Dict[str, list], key: str) -> bool:
    now = time.time()
    history = [t for t in store.get(key, []) if now - t < 3600]
    if len(history) >= 3:
        store[key] = history
        return False
    history.append(now)
    store[key] = history
    return True


@router.post("/reset/request")
async def reset_request_route(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Déclenche l'envoi d'un mail Keycloak `UPDATE_PASSWORD`.
    Réponse uniforme (200) qu'un compte existe ou non, pour empêcher l'énumération."""
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"reset:{client_ip}"
    if not _check_rate_limit(_RESET_RATE_LIMIT, rate_key):
        await logs_service.add_logs(
            action="RESET_REQUEST_RATE_LIMITED",
            log_level="WARNING",
            user_id="system",
            user_role="unknown",
            patient_id="null",
            message="Rate limit exceeded for password reset requests",
        )
        # On répond quand même 200 pour rester non-distinguable.
        return {"status": "ok"}

    auth_service = AuthService(db=db)
    try:
        auth_service.send_credentials_reset_email(payload.email)
        await logs_service.add_logs(
            action="RESET_REQUEST_SENT",
            log_level="INFO",
            user_id=payload.email,
            user_role="unknown",
            patient_id="null",
            message="Password reset email sent",
        )
    except Exception as exc:
        # Trace serveur pour debug ; le client reste à 200 pour anti-énumération.
        traceback.print_exc()
        await logs_service.add_logs(
            action=f"RESET_REQUEST_FAIL:{type(exc).__name__}:{str(exc)[:200]}",
            log_level="WARNING",
            user_id=payload.email,
            user_role="unknown",
            patient_id="null",
            message=f"Failed to send password reset email: {str(exc)}",
        )
    return {"status": "ok"}


@router.post("/add_device/request")
async def add_device_request_route(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Envoie un email Keycloak pour enregistrer un nouveau passkey WebAuthn sur un
    nouvel appareil, SANS supprimer les passkeys existants sur les autres appareils.
    Réponse uniforme (200) pour empêcher l'énumération."""
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"add_device:{client_ip}"
    if not _check_rate_limit(_ADD_DEVICE_RATE_LIMIT, rate_key):
        await logs_service.add_logs(
            action="ADD_DEVICE_REQUEST_RATE_LIMITED",
            log_level="WARNING",
            user_id="system",
            user_role="unknown",
            patient_id="null",
            message="Rate limit exceeded for add device requests",
        )
        return {"status": "ok"}

    auth_service = AuthService(db=db)
    try:
        auth_service.send_add_device_email(payload.email)
        await logs_service.add_logs(
            action="ADD_DEVICE_REQUEST_SENT",
            log_level="INFO",
            user_id=payload.email,
            user_role="unknown",
            patient_id="null",
            message="Add device email sent",
        )
    except Exception as exc:
        traceback.print_exc()
        await logs_service.add_logs(
            action=f"ADD_DEVICE_REQUEST_FAIL",
            log_level="WARNING",
            user_id=payload.email,
            user_role="unknown",
            patient_id="null",
            message=f"Failed to send add device email: {str(exc)}",
        )
    return {"status": "ok"}


@router.post("/reset/with-certificate")
async def reset_with_certificate_route(
    body: ChallengeResponseRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Reset par certificat médecin : on vérifie la signature du challenge,
    puis Keycloak force un changement de mot de passe à la prochaine connexion."""
    auth_service = AuthService(db=db)
    try:
        auth_service.verify_challenge_response(
            username=body.username,
            nonce=body.nonce,
            timestamp=body.timestamp,
            signature=body.signature,
            certificate=body.certificate,
        )
        auth_service.force_credentials_reset(body.username)
        await logs_service.add_logs(
            action="RESET_WITH_CERTIFICATE",
            log_level="INFO",
            user_id=body.username,
            user_role="doctor",
            patient_id="null",
            message="Credentials reset via certificate",
        )
        return {"status": "ok"}
    except Exception as e:
        auth_service.clear_challenge(username=body.username)
        await logs_service.add_logs(
            action="RESET_WITH_CERTIFICATE_FAIL",
            log_level="WARNING",
            user_id=body.username,
            user_role="doctor",
            patient_id="null",
            message=str(e),
        )
        raise HTTPException(status_code=400, detail=f"Échec reset par certificat : {str(e)}")
