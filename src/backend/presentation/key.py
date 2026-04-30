"""
Module de gestion des clés pour l'application FastAPI. 
Ce module fournit des routes pour gérer les clés, valider les tokens JWT, et extraire les informations utilisateur à partir du token d'authentification. 
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Form
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from schema.auth_schema import UserInDB
from core.database import get_db
from core.auth import get_current_user
from typing import Dict, Any
from service.log_service import LogsService
from service.key_service import KeyService
from sqlalchemy.orm import Session
from schema.key_schema import KeyBase, KeyResponse
from schema.device_schema import DeviceRegister

router = APIRouter( # Créer un routeur APIRouter pour les routes de gestion des clés
    prefix="/keys",
    tags=["keys"]
)
load_dotenv()
logs_service = LogsService()

@router.post("/register_device", response_model=Dict[str, Any])
def register_device_route(
    device_data: DeviceRegister = Form(...),
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        key_service = KeyService(db=db)
        device = key_service.register_device(user_id=current_user.id, device_name=device_data.name, public_key=device_data.public_key)
        logs_service.add_logs(action="REGISTER_DEVICE", log_level="INFO", user_id=current_user.id, user_role="unknown", patient_id="null")
        return {"device_id": device.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'enregistrement du dispositif: {str(e)}")

@router.post("/store_kek", response_model=Dict[str, Any])
def store_device_keys_route(
    key_data: KeyBase = Form(...),
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        key_service = KeyService(db=db)
        key_service.store_device_keys(user_id=current_user.id, ciphered_kek=key_data.ciphered_kek, device_id=key_data.device_id)
        logs_service.add_logs(action="STORE_DEVICE_KEYS", log_level="INFO", user_id=current_user.id, user_role="unknown", patient_id="null")
        return {"status": "Clés stockées avec succès pour le dispositif"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors du stockage des clés: {str(e)}")

@router.get("/get_device_keys", response_model=KeyResponse)
def get_device_keys_route(
    device_id: str = Query(..., description="ID du dispositif dont les clés doivent être récupérées"),
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> KeyResponse:
    try:
        key_service = KeyService(db=db)
        device_keys = key_service.get_device_keys(user_id=current_user.id, device_id=device_id)
        logs_service.add_logs(action="GET_DEVICE_KEYS", log_level="INFO", user_id=current_user.id, user_role="unknown", patient_id="null")
        return device_keys
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la récupération des clés: {str(e)}")

@router.get("/get_device_public_key", response_model=Dict[str, str])
def get_device_public_key_route(
    target_user_id: str = Query(..., description="ID de l'utilisateur dont la clé publique doit être récupérée"),
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, str]:
    try:
        key_service = KeyService(db=db)
        user_keys = key_service.get_device_public_key(user_id=target_user_id)
        logs_service.add_logs(action="GET_DEVICE_PUBLIC_KEY", log_level="INFO", user_id=current_user.id, user_role="unknown", patient_id="null")
        return {"public_key": user_keys.public_key}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la récupération de la clé publique: {str(e)}")