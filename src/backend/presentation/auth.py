from fastapi import APIRouter, Depends, HTTPException, Query
from dotenv import load_dotenv
from core.database import get_db
from core.auth import get_current_user, validate_jwt_token, get_username_from_token
from typing import Dict, Any

from src.backend.schema.auth_schema import UserInDB

router = APIRouter( # Créer un routeur APIRouter pour les routes de gestion de l'authentification
    prefix="/auth",
    tags=["auth"]
)
load_dotenv()

@router.get("/validate_token", response_model=Dict[str, Any])
async def validate_token_route(token: str = Query(..., description="JWT token to validate")) -> Dict[str, Any]:
    try:
        paylod = await validate_jwt_token(token)
        return {"status": "Token valide",
                "payload": paylod}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la validation du token: {str(e)}")

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
