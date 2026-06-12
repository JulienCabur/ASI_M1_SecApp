"""Gestion du compte utilisateur : suppression complète (droit à l'effacement RGPD)."""

import os
from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.session import clear_session_cookie
from schema.auth_schema import UserInDB
from service.auth_service import AuthService
from service.log_service import LogsService

router = APIRouter()
logs_service = LogsService("backend_auth")


@router.delete("/account")
async def delete_account_route(
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user),
) -> JSONResponse:
    """Supprime toutes les données de l'utilisateur authentifié (Art. 17 RGPD)."""
    user_id = str(current_user.id)
    storage_path = os.getenv("STORAGE_PATH", "/storage")

    auth_service = AuthService(db=db)
    auth_service.erase_user_data(user_id=user_id, storage_path=storage_path)

    await logs_service.add_logs(
        action="ACCOUNT_ERASED",
        log_level="INFO",
        user_id=user_id,
        user_role=(current_user.roles[0] if current_user.roles else "unknown"),
        patient_id="null",
        message="Toutes les données utilisateur ont été supprimées (Art. 17 RGPD)",
    )

    response = JSONResponse({"status": "account_deleted"})
    clear_session_cookie(response)
    return response
