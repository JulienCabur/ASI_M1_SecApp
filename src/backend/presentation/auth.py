from fastapi import APIRouter, Query
from dotenv import load_dotenv
from core.database import get_db
from core.auth import validate_jwt_token
from typing import Dict, Any

router = APIRouter( # Créer un routeur APIRouter pour les routes de gestion des fichiers
    prefix="/auth",
    tags=["auth"]
)
load_dotenv()

@router.get("/validate-token", response_model=Dict[str, Any])
async def validate_token_route(token: str = Query(..., description="JWT token to validate")) -> Dict[str, Any]:
    print(f"🔐 Token reçu: {token[:50]}...")
    try:
        print("Appel validate_jwt_token...")
        payload = await validate_jwt_token(token)
        print(f"✅ Payload reçu: {payload}")
        return {
            "status": "Token valide",
            "payload": payload,
            "user_id": payload.get("sub"),
            "username": payload.get("preferred_username") or payload.get("name"),
            "email": payload.get("email"),
            "roles": payload.get("realm_access", {}).get("roles", []),
        }
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        raise