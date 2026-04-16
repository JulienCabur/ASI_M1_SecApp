import os
import httpx
import jwt
from typing import Any, Dict
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from schema.auth_schema import UserInDB
from dotenv import load_dotenv

load_dotenv()

security = HTTPBearer()


async def get_keycloak_public_key() -> Dict[str, Any]:
    """
    Récupère la clé publique de Keycloak via son endpoint JWKS (JSON Web Key Set).
    Cette clé est utilisée pour vérifier la signature du JWT.
    """
    try:
        keycloak_url = os.getenv("KEYCLOAK_PUBLIC_KEY_URL")
        
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(keycloak_url)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service d'authentification indisponible")

async def get_public_key(token: str) -> Dict[str, Any]:
    """
    Récupère la clé publique correspondante au token JWT en utilisant le kid du header du token pour trouver la bonne clé dans le JWKS de Keycloak.
    """
    try:
        jwks = await get_keycloak_public_key()
        unverified_header = jwt.get_unverified_header(token)
        key_id = unverified_header.get("kid")

        if not key_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")

        public_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == key_id and public_key is None:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)

        if not public_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Clé de signature non trouvée")

        return public_key

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Erreur lors de la récupération de la clé publique: {str(e)}")

async def validate_jwt_token(token: str) -> Dict[str, Any]:
    """
    Valide un JWT donné en paramètre en vérifiant sa signature avec les clés publiques de Keycloak.
    Retourne le payload du token si valide, ou lève une HTTPException.
    """
    try:
        public_key = await get_public_key(token)
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False}
        )
        return payload

    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token expiré: {str(e)}")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token invalide: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Erreur lors de la validation du token: {str(e)}")


async def get_current_user(credentials: Any = Depends(security)) -> UserInDB:
    """
    Dépendance FastAPI pour vérifier l'authentification.
    """
    try:

        public_key = await get_public_key(credentials.credentials)
        payload = jwt.decode(
            credentials.credentials,
            public_key,
            algorithms=["RS256"],
            audience=os.getenv("KEYCLOAK_CLIENT_ID") if os.getenv("KEYCLOAK_CLIENT_ID") else None,
            options={"verify_aud": bool(os.getenv("KEYCLOAK_CLIENT_ID"))}
        )
        user = UserInDB(
            id=payload.get("sub"),
            username=payload.get("preferred_username") or payload.get("name"),
            email=payload.get("email", ""),
            roles=payload.get("realm_access", {}).get("roles", [])
        )
        return user

    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token expiré : {e}")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token invalide : {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Erreur d'authentification : {e}")
