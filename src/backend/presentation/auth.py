"""
Module de gestion de l'authentification pour l'application FastAPI. 
Ce module fournit des routes pour valider les tokens JWT, enregistrer les médecins, et extraire les informations utilisateur à partir du token d'authentification. 
Il utilise des services d'authentification et de journalisation pour gérer les opérations liées à l'authentification et enregistrer les événements importants.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Form
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from core.database import get_db
from core.auth import get_current_user, validate_jwt_token
from typing import Dict, Any
from service.log_service import LogsService
from service.auth_service import AuthService
from sqlalchemy.orm import Session
from schema.auth_schema import UserInDB, CertificateRequest
import time

router = APIRouter( # Créer un routeur APIRouter pour les routes de gestion de l'authentification
    prefix="/auth",
    tags=["auth"]
)
load_dotenv()
logs_service = LogsService()
@router.get("/validate_token", response_model=Dict[str, Any])
async def validate_token_route(token: str = Query(..., description="JWT token to validate")) -> Dict[str, Any]:
    try:
        payload = await validate_jwt_token(token)
        return {"status": "Token valide",
                "payload": payload}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la validation du token: {str(e)}")

@router.post("/register_doctor", response_model=Dict[str, Any])
async def register_doctor_route(
    user_info: CertificateRequest = Form(...),
    db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        auth_service = AuthService(db=db)
        print(f"Enregistrement du médecin: {user_info.username}")
        auth_service.generate_csr(user_info.username)
        print(f"CSR généré pour le médecin: {user_info.username}")
        time.sleep(5)  # Attendre que le CSR soit signé
        cert_path = auth_service.check_csr_signed(user_info.username)
        print(f"CSR signé pour le médecin: {user_info.username}, chemin du certificat: {cert_path}")
        auth_service.create_doctor_in_keycloak(cert_path, user_info)
        print(f"Docteur créé dans Keycloak pour le médecin: {user_info.username}")
        return FileResponse(path=cert_path, filename=f"{user_info.username}.p12", media_type="application/x-pkcs12")
        auth_service.delete_sensitive_files(user_info.username)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'enregistrement du médecin: {str(e)}")

@router.get("/user_info", response_model=Dict[str, Any])
async def get_user_info_route(current_user: UserInDB = Depends(get_current_user)) -> Dict[str, Any]:
    try:
        return {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "roles": current_user.roles
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'extraction des informations utilisateur: {str(e)}")

@router.get("/user_name", response_model=Dict[str, Any])
async def get_username_route(current_user: UserInDB = Depends(get_current_user)) -> Dict[str, Any]:
    try:
        return {"username": current_user.username}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'extraction du nom d'utilisateur: {str(e)}")

@router.get("/user_roles", response_model=Dict[str, Any])
async def get_user_roles_route(current_user: UserInDB = Depends(get_current_user)) -> Dict[str, Any]:
    try:
        return {"roles": current_user.roles}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'extraction des rôles utilisateur: {str(e)}")
