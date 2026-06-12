"""Routes pour la consultation de la liste des hôpitaux disponibles."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from service.hospitals import HospitalService
from core.database import get_db
from core.auth import get_current_user
from service.file_service import FileService
from schema.auth_schema import UserInDB
from schema.file_schema import FileBase
from typing import Dict, Any, Optional
from service.log_service import LogsService
import os

router = APIRouter(
    prefix="/hospitals",
    tags=["hospitals"]
)
load_dotenv()
log_service = LogsService("backend_hospitals")

@router.get("/list", response_model=Dict[str, Any])
async def list_hospitals(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retourne la liste de tous les hôpitaux enregistrés en base."""
    try:
        hospital_service = HospitalService(db=db)
        hospitals = hospital_service.get_hospitals()
        log_service.add_logs(action="LIST_HOSPITALS", log_level="INFO", user_id="null", user_role="null", patient_id="null")
        return {"hospitals": hospitals}
    except Exception as e:
        log_service.add_logs(action=f"LIST_HOSPITALS_FAIL:{type(e).__name__}:{str(e)}", log_level="ERROR", user_id="null", user_role="null", patient_id="null")
        raise HTTPException(status_code=400, detail=f"Erreur lors de la récupération de la liste des hôpitaux: {str(e)}")
