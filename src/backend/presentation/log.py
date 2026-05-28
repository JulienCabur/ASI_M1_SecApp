"""
Ce module définit les endpoints API pour la gestion des logs du service.
Il inclut des fonctionnalités pour récupérer les logs selon différents critères.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from core.auth import get_current_user
from schema.auth_schema import UserInDB
from service.log_service import LogsService

router = APIRouter( # Crée un routeur APIRouter pour les routes liées aux logs
    prefix="/logs",
    tags=["logs"],
)

log_service = LogsService()

@router.post("/add_log")
async def post_logs(
    action: str = Query(..., description="Message du log à écrire", example="Ceci est un message de log web"),
    log_level: str = Query(..., description="Niveau du log (e.g., INFO, ERROR)", example="INFO"),
    patient_id: str = Query("null", description="ID du patient associé au log, ou 'null' si non applicable", example="12345"),
    current_user: UserInDB = Depends(get_current_user)
    ):
    """
    Endpoint pour ajouter un log à Logstash.
    """
    try:
        web_logs = await log_service.add_logs(action=action, log_level=log_level, user_id=str(current_user.id), user_role=current_user.roles[0], patient_id=patient_id)
        if not web_logs:
            await log_service.add_logs(action="ADD_LOG_ERROR", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id=patient_id)
            raise HTTPException(status_code=404, detail="Cannot write web logs")
        return {"message": "Log added successfully"}
    except Exception as e:
        await log_service.add_logs(action="ADD_LOG_EXCEPTION", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id=patient_id, message=str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")
