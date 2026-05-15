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

# Rate-limit en mémoire (process-local). Pour du multi-worker, déplacer vers Redis.
_RESET_RATE_LIMIT: Dict[str, list] = {}
_RESET_RATE_LIMIT_WINDOW = 3600  # 1h
_RESET_RATE_LIMIT_MAX = 3


def _check_reset_rate_limit(key: str) -> bool:
    now = time.time()
    history = [t for t in _RESET_RATE_LIMIT.get(key, []) if now - t < _RESET_RATE_LIMIT_WINDOW]
    if len(history) >= _RESET_RATE_LIMIT_MAX:
        _RESET_RATE_LIMIT[key] = history
        return False
    history.append(now)
    _RESET_RATE_LIMIT[key] = history
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
    if not _check_reset_rate_limit(rate_key):
        logs_service.add_logs(
            action="RESET_REQUEST_RATE_LIMITED",
            log_level="WARNING",
            user_id="système",
            user_role="unknown",
            patient_id="null",
        )
        # On répond quand même 200 pour rester non-distinguable.
        return {"status": "ok"}

    auth_service = AuthService(db=db)
    try:
        auth_service.send_credentials_reset_email(payload.email)
        logs_service.add_logs(
            action="RESET_REQUEST_SENT",
            log_level="INFO",
            user_id=payload.email,
            user_role="unknown",
            patient_id="null",
        )
    except Exception as exc:
        # Trace serveur pour debug ; le client reste à 200 pour anti-énumération.
        traceback.print_exc()
        logs_service.add_logs(
            action=f"RESET_REQUEST_FAIL:{type(exc).__name__}:{str(exc)[:200]}",
            log_level="WARNING",
            user_id=payload.email,
            user_role="unknown",
            patient_id="null",
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
        logs_service.add_logs(
            action="RESET_WITH_CERTIFICATE",
            log_level="INFO",
            user_id=body.username,
            user_role="doctor",
            patient_id="null",
        )
        return {"status": "ok"}
    except Exception as e:
        auth_service.clear_challenge(username=body.username)
        logs_service.add_logs(
            action="RESET_WITH_CERTIFICATE_FAIL",
            log_level="WARNING",
            user_id=body.username,
            user_role="doctor",
            patient_id="null",
        )
        raise HTTPException(status_code=400, detail=f"Échec reset par certificat : {str(e)}")
