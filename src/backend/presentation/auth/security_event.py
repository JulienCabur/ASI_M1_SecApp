"""Réception des événements de sécurité remontés par le navigateur (whistleblower).

Le frontend détecte des comportements suspects (DevTools ouverts, timestamps
incohérents, tentatives de manipulation du DOM) et les reporte ici.
On logue dans la chaîne d'audit sans bloquer la requête : l'objectif est la
détection a posteriori et l'alerte, pas l'interruption de l'UX.
"""

from typing import Any, Dict

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from service.log_service import LogsService

router = APIRouter()
logs_service = LogsService("backend_security")

_ALLOWED_EVENT_TYPES = {
    "DEVTOOLS_OPENED",
    "CLIPBOARD_EXFILTRATION",
    "RAPID_NAVIGATION",
    "VISIBILITY_ANOMALY",
    "RIGHT_CLICK_SENSITIVE",
    "KEYBOARD_SHORTCUT_BLOCKED",
    "CONSOLE_TAMPERING",
    "IFRAME_INJECTION_ATTEMPT",
    "DOM_MUTATION_SUSPICIOUS",
    "FOCUS_BLUR_PATTERN",
}


class SecurityEventPayload(BaseModel):
    event_type: str = Field(..., max_length=64)
    detail: str = Field(default="", max_length=512)
    client_ts: str = Field(default="", max_length=64)


@router.post("/security-event")
async def security_event_route(
    body: SecurityEventPayload,
    request: Request,
) -> Dict[str, Any]:
    """Reçoit un événement de sécurité depuis le navigateur et le logue."""
    client_ip = request.client.host if request.client else "unknown"
    event_type = body.event_type.upper().replace(" ", "_")
    if event_type not in _ALLOWED_EVENT_TYPES:
        event_type = "UNKNOWN_CLIENT_EVENT"

    await logs_service.add_logs(
        action=f"CLIENT_SECURITY_EVENT:{event_type}",
        log_level="WARNING",
        user_id=client_ip,
        user_role="unknown",
        patient_id="null",
        message=body.detail[:512],
    )
    return {"status": "received"}
