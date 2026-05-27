"""
Module de gestion des clés pour l'application FastAPI. 
Ce module fournit des routes pour gérer les clés, valider les tokens JWT, et extraire les informations utilisateur à partir du token d'authentification. 
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Form
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from schema.auth_schema import UserInDB
from core.database import get_db
from core.auth import get_current_user
from typing import Dict, Any, List
from service.log_service import LogsService
from service.device_service import DeviceService
from sqlalchemy.orm import Session
from schema.key_schema import KeyBase, KeyResponse
from schema.device_schema import DeviceRegister, DeviceResponse

router = APIRouter( # Créer un routeur APIRouter pour les routes de gestion des clés
    prefix="/keys",
    tags=["keys"]
)
load_dotenv()
logs_service = LogsService("backend_devices")

@router.post("/register_device", response_model=Dict[str, Any])
async def register_device_route(
    device_data: DeviceRegister,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        jwk = device_data.public_key
        if jwk.kty != "RSA" or jwk.e != "AQAB" or len(jwk.n) != 683 or not re.fullmatch(r'[A-Za-z0-9_\-]+', jwk.n):
            await logs_service.add_logs(action="REGISTER_DEVICE_INVALID_PUBLIC_KEY", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
            raise HTTPException(status_code=400, detail="La clé publique doit être une clé RSA-OAEP 4096 bits valide.")

        device_service = DeviceService(db=db)
        device = device_service.register_device(user_id=current_user.id, device_name=device_data.name, public_key=device_data.public_key.model_dump())
        await logs_service.add_logs(action="REGISTER_DEVICE", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
        return {"device_id": device.id, "is_verified": device.is_verified}
    except Exception as e:
        await logs_service.add_logs(action="REGISTER_DEVICE_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'enregistrement du dispositif: {str(e)}")

@router.post("/store_kek", response_model=Dict[str, Any])
async def store_device_keys_route(
    key_data: KeyBase = Form(...),
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        if len(key_data.ciphered_kek) != 684:
            await logs_service.add_logs(action="STORE_DEVICE_KEYS_INVALID_KEK", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
            raise HTTPException(status_code=400, detail="Le KEK chiffré doit être une chaîne base64 de 684 caractères (684 bytes).")

        device_service = DeviceService(db=db)
        device_service.store_device_keys(user_id=current_user.id, ciphered_kek=key_data.ciphered_kek, device_id=key_data.device_id)
        await logs_service.add_logs(action="STORE_DEVICE_KEYS", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
        return {"status": "Clés stockées avec succès pour le dispositif"}
    except Exception as e:
        await logs_service.add_logs(action="STORE_DEVICE_KEYS_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
        raise HTTPException(status_code=400, detail=f"Erreur lors du stockage des clés: {str(e)}")

@router.get("/get_device_keys", response_model=KeyResponse)
async def get_device_keys_route(
    device_id: str = Query(..., description="ID du dispositif dont les clés doivent être récupérées"),
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> KeyResponse:
    try:
        device_service = DeviceService(db=db)
        device_keys = device_service.get_device_keys(user_id=current_user.id, device_id=device_id)
        await logs_service.add_logs(action="GET_DEVICE_KEYS", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
        return device_keys
    except Exception as e:
        await logs_service.add_logs(action="GET_DEVICE_KEYS_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
        raise HTTPException(status_code=400, detail=f"Erreur lors de la récupération des clés: {str(e)}")

@router.get("/list_unverified_devices", response_model=List[DeviceResponse])
async def list_unverified_devices_route(
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> List[DeviceResponse]:
    try:
        device_service = DeviceService(db=db)
        unverified_devices = device_service.list_unverified_devices(user_id=current_user.id)
        await logs_service.add_logs(action="LIST_UNVERIFIED_DEVICES", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
        return unverified_devices
    except Exception as e:
        await logs_service.add_logs(action="LIST_UNVERIFIED_DEVICES_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
        raise HTTPException(status_code=400, detail=f"Erreur lors de la liste des dispositifs non vérifiés: {str(e)}")

@router.post("/verify_device", response_model=Dict[str, Any])
async def verify_device_route(
    device_id: str = Form(..., description="ID du dispositif à vérifier"),
    ciphered_kek: str = Form(..., description="KEK chiffré du dispositif à vérifier"),
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        device_service = DeviceService(db=db)
        device = device_service.verify_device(user_id=current_user.id, device_id=device_id, ciphered_kek=ciphered_kek)
        await logs_service.add_logs(action="VERIFY_DEVICE", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
        return {"device_id": device.id, "is_verified": device.is_verified}
    except Exception as e:
        await logs_service.add_logs(action="VERIFY_DEVICE_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
        raise HTTPException(status_code=400, detail=f"Erreur lors de la vérification du dispositif: {str(e)}")

@router.get("/list_verified_devices", response_model=List[DeviceResponse])
async def list_verified_devices_route(
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> List[DeviceResponse]:
    try:
        device_service = DeviceService(db=db)
        verified_devices = device_service.list_verified_devices(user_id=current_user.id)
        await logs_service.add_logs(action="LIST_VERIFIED_DEVICES", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
        return verified_devices
    except Exception as e:
        await logs_service.add_logs(action="LIST_VERIFIED_DEVICES_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
        raise HTTPException(status_code=400, detail=f"Erreur lors de la liste des dispositifs vérifiés: {str(e)}")

@router.post("/reject_device", response_model=Dict[str, Any])
async def reject_device_route(
    device_id: str = Form(..., description="ID du dispositif à refuser"),
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        device_service = DeviceService(db=db)
        device_service.reject_device(user_id=current_user.id, device_id=device_id)
        await logs_service.add_logs(action="REJECT_DEVICE", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
        return {"status": "Dispositif refusé avec succès"}
    except Exception as e:
        await logs_service.add_logs(action="REJECT_DEVICE_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
        raise HTTPException(status_code=400, detail=f"Erreur lors du refus du dispositif: {str(e)}")

@router.post("/revoke_device", response_model=Dict[str, Any])
async def revoke_device_route(
    device_id: str = Form(..., description="ID du dispositif à révoquer"),
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        device_service = DeviceService(db=db)
        device_service.revoke_device(user_id=current_user.id, device_id=device_id)
        await logs_service.add_logs(action="REVOKE_DEVICE", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
        return {"status": "Dispositif révoqué avec succès"}
    except Exception as e:
        await logs_service.add_logs(action="REVOKE_DEVICE_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
        raise HTTPException(status_code=400, detail=f"Erreur lors de la révocation du dispositif: {str(e)}")
