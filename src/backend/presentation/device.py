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
from typing import Dict, Any, List
from service.log_service import LogsService
from service.device_service import DeviceService
from service.sse_service import sse_manager
from sqlalchemy.orm import Session
from schema.key_schema import KeyBase, KeyResponse
from schema.device_schema import DeviceRegister, DeviceResponse

router = APIRouter( # Créer un routeur APIRouter pour les routes de gestion des clés
    prefix="/keys",
    tags=["keys"]
)
load_dotenv()
logs_service = LogsService()

@router.post("/register_device", response_model=Dict[str, Any])
def register_device_route(
    device_data: DeviceRegister,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        device_service = DeviceService(db=db)
        device = device_service.register_device(user_id=current_user.id, device_name=device_data.name, public_key=device_data.public_key.model_dump())
        logs_service.add_logs(action="REGISTER_DEVICE", log_level="INFO", user_id=current_user.id, user_role="unknown", patient_id="null")
        if not device.is_verified:
            sse_manager.publish(current_user.id, "device_pending", {
                "device_id": device.id,
                "device_name": device.device_name,
                "is_verified": device.is_verified,
            })
        return {"device_id": device.id, "is_verified": device.is_verified}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'enregistrement du dispositif: {str(e)}")

@router.post("/store_kek", response_model=Dict[str, Any])
def store_device_keys_route(
    key_data: KeyBase = Form(...),
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        device_service = DeviceService(db=db)
        device_service.store_device_keys(user_id=current_user.id, ciphered_kek=key_data.ciphered_kek, device_id=key_data.device_id)
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
        device_service = DeviceService(db=db)
        device_keys = device_service.get_device_keys(user_id=current_user.id, device_id=device_id)
        logs_service.add_logs(action="GET_DEVICE_KEYS", log_level="INFO", user_id=current_user.id, user_role="unknown", patient_id="null")
        return device_keys
    except Exception as e:
        if "non trouvé" in str(e):
            raise HTTPException(status_code=404, detail="Dispositif non trouvé")
        raise HTTPException(status_code=400, detail=f"Erreur lors de la récupération des clés: {str(e)}")

@router.get("/list_devices", response_model=List[DeviceResponse])
def list_devices_route(
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> List[DeviceResponse]:
    try:
        device_service = DeviceService(db=db)
        devices = device_service.list_all_devices(user_id=current_user.id)
        logs_service.add_logs(action="LIST_DEVICES", log_level="INFO", user_id=current_user.id, user_role="unknown", patient_id="null")
        return devices
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la liste des dispositifs: {str(e)}")

@router.get("/list_unverified_devices", response_model=List[DeviceResponse])
def list_unverified_devices_route(
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> List[DeviceResponse]:
    try:
        device_service = DeviceService(db=db)
        unverified_devices = device_service.list_unverified_devices(user_id=current_user.id)
        logs_service.add_logs(action="LIST_UNVERIFIED_DEVICES", log_level="INFO", user_id=current_user.id, user_role="unknown", patient_id="null")
        return unverified_devices
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la liste des dispositifs non vérifiés: {str(e)}")

@router.post("/verify_device", response_model=Dict[str, Any])
def verify_device_route(
    device_id: str = Form(..., description="ID du dispositif à vérifier"),
    ciphered_kek: str = Form(..., description="KEK chiffré du dispositif à vérifier"),
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        device_service = DeviceService(db=db)
        device = device_service.verify_device(user_id=current_user.id, device_id=device_id, ciphered_kek=ciphered_kek)
        logs_service.add_logs(action="VERIFY_DEVICE", log_level="INFO", user_id=current_user.id, user_role="unknown", patient_id="null")
        sse_manager.publish(current_user.id, "device_approved", {
            "device_id": device.id,
            "is_verified": device.is_verified,
            "ciphered_kek": device.ciphered_kek,
        })
        return {"device_id": device.id, "is_verified": device.is_verified}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la vérification du dispositif: {str(e)}")

@router.post("/revoke_device", response_model=Dict[str, Any])
def revoke_device_route(
    device_id: str = Form(..., description="ID du dispositif à révoquer"),
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        device_service = DeviceService(db=db)
        device_service.revoke_device(user_id=current_user.id, device_id=device_id)
        logs_service.add_logs(action="REVOKE_DEVICE", log_level="INFO", user_id=current_user.id, user_role="unknown", patient_id="null")
        sse_manager.publish(current_user.id, "device_revoked", {"device_id": device_id})
        return {"status": "Dispositif révoqué"}
    except Exception as e:
        if "non trouvé" in str(e):
            raise HTTPException(status_code=404, detail="Dispositif non trouvé")
        raise HTTPException(status_code=400, detail=f"Erreur lors de la révocation du dispositif: {str(e)}")

@router.post("/reject_device", response_model=Dict[str, Any])
def reject_device_route(
    device_id: str = Form(..., description="ID du dispositif à rejeter"),
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        device_service = DeviceService(db=db)
        device_service.reject_device(user_id=current_user.id, device_id=device_id)
        logs_service.add_logs(action="REJECT_DEVICE", log_level="INFO", user_id=current_user.id, user_role="unknown", patient_id="null")
        sse_manager.publish(current_user.id, "device_rejected", {"device_id": device_id})
        return {"status": "Dispositif rejeté"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors du rejet du dispositif: {str(e)}")
