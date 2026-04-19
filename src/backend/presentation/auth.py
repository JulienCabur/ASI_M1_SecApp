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
from schema.auth_schema import UserInDB, CertificateRequest, ChallengeResponse, ChallengeResponseRequest
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
        logs_service.add_logs(action="VALIDATE_TOKEN", log_level="INFO", user_id=payload.get("sub"), user_role=payload.get("roles", ["unknown"])[0], patient_id="null")
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
        auth_service.generate_csr(user_info.username)
        logs_service.add_logs(action="GENERATE_CSR", log_level="INFO", user_id=user_info.username, user_role="doctor", patient_id="null")
        time.sleep(5)
        cert_path = auth_service.check_csr_signed(user_info.username)
        logs_service.add_logs(action="CHECK_CSR_SIGNED", log_level="INFO", user_id=user_info.username, user_role="doctor", patient_id="null")
        auth_service.create_doctor_in_keycloak(cert_path, user_info)
        logs_service.add_logs(action="REGISTER_DOCTOR", log_level="INFO", user_id=user_info.username, user_role="doctor", patient_id="null")
        return FileResponse(path=cert_path, filename=f"{user_info.username}.p12", media_type="application/x-pkcs12")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'enregistrement du médecin: {str(e)}")

@router.get("/password_for_cert", response_model=Dict[str, Any])
async def get_password_for_cert_route(
    username: str = Query(..., description="Nom d'utilisateur pour lequel récupérer le mot de passe"),
    db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        auth_service = AuthService(db=db)
        password = auth_service.get_password_for_cert(username)
        logs_service.add_logs(action="GET_PASSWORD_FOR_CERT", log_level="INFO", user_id=username, user_role="doctor", patient_id="null")
        auth_service.delete_sensitive_files(username)
        logs_service.add_logs(action="DELETE_SENSITIVE_FILES", log_level="INFO", user_id=username, user_role="doctor", patient_id="null")
        return {"password": password}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la récupération du mot de passe: {str(e)}")

@router.get("/challenge", response_model=ChallengeResponse)
async def get_challenge(
    username: str = Query(..., description="Nom d'utilisateur pour lequel générer le challenge"),
    db: Session = Depends(get_db)) -> ChallengeResponse:
    auth_service = AuthService(db=db)
    challenge = auth_service.generate_challenge(username)
    return challenge

@router.post("/challenge_response", response_model=Dict[str, Any])
async def post_challenge_response(
    ChallengeResponseRequest: ChallengeResponseRequest,
    db: Session = Depends(get_db)) -> Dict[str, Any]:
    auth_service = AuthService(db=db)
    try :
        auth_service.verify_challenge_response(
            username=ChallengeResponseRequest.username,
            nonce=ChallengeResponseRequest.nonce,
            timestamp=ChallengeResponseRequest.timestamp,
            signature=ChallengeResponseRequest.signature,
            certificate=ChallengeResponseRequest.certificate
        )
        return {"status": "Challenge response received"}
    except Exception as e:
        auth_service.clear_challenge(username=ChallengeResponseRequest.username)
        raise HTTPException(status_code=400, detail=f"Erreur lors de la soumission de la réponse au challenge: {str(e)}")

@router.get("/user_info", response_model=Dict[str, Any])
async def get_user_info_route(current_user: UserInDB = Depends(get_current_user)) -> Dict[str, Any]:
    try:
        logs_service.add_logs(action="GET_USER_INFO", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
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
        logs_service.add_logs(action="GET_USERNAME", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
        return {"username": current_user.username}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'extraction du nom d'utilisateur: {str(e)}")

@router.get("/user_roles", response_model=Dict[str, Any])
async def get_user_roles_route(current_user: UserInDB = Depends(get_current_user)) -> Dict[str, Any]:
    try:
        logs_service.add_logs(action="GET_USER_ROLES", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], patient_id="null")
        return {"roles": current_user.roles}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'extraction des rôles utilisateur: {str(e)}")
