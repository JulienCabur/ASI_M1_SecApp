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
        print(f"📍 URL JWKS: {keycloak_url}")
        
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(keycloak_url)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        print(f"❌ Erreur HTTP Keycloak: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service d'authentification indisponible")


async def validate_jwt_token(token: str) -> Dict[str, Any]:
    """
    Valide un JWT donné en paramètre en vérifiant sa signature avec les clés publiques de Keycloak.
    Retourne le payload du token si valide, ou lève une HTTPException.
    """
    try:
        print(f"1️⃣ Récupération JWKS de Keycloak...")
        # Récupère la clé publique de Keycloak
        jwks = await get_keycloak_public_key()
        print(f"2️⃣ JWKS reçu: {len(jwks.get('keys', []))} clés")
        
        # Extrait le header du token (sans vérifier) pour obtenir le kid
        print(f"3️⃣ Extraction du header du token...")
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        print(f"4️⃣ KID extrait: {kid}")
        
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Token invalide: pas de 'kid' dans le header JWT"
            )
        
        # Trouve la clé correspondante dans le JWKS
        print(f"5️⃣ Recherche de la clé correspondant à kid={kid}")
        public_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                print(f"6️⃣ Clé trouvée! Construction de la clé RSA...")
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                break
        
        if not public_key:
            print(f"❌ Clé non trouvée pour kid={kid}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail=f"Clé de signature avec kid '{kid}' non trouvée dans Keycloak"
            )
        
        # Valide et décode le token avec la clé publique
        print(f"7️⃣ Vérification de la signature RS256...")
        # Note: On ne vérifie pas l'audience (verify_aud=False) car Keycloak utilise 'account' par défaut
        # et cela peut être différent du CLIENT_ID. L'important est de valider la signature RS256.
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False}  # Désactiver la vérification d'audience
        )
        print(f"8️⃣ ✅ Token valide! Payload: {payload.get('sub')}")
        
        return payload
        
    except jwt.ExpiredSignatureError as e:
        print(f"❌ Token expiré: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail=f"❌ Token expiré: {str(e)}"
        )
    except jwt.InvalidTokenError as e:
        print(f"❌ Token invalide: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail=f"❌ Token invalide: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erreur générale: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"❌ Erreur lors de la validation du token: {str(e)}"
        )

async def get_current_user(credentials: Any = Depends(security)) -> UserInDB:
    """
    Dépendance FastAPI pour vérifier l'authentification.
    """
    try:
        jwks = await get_keycloak_public_key()
        unverified_header = jwt.get_unverified_header(credentials.credentials)
        kid = unverified_header.get("kid")

        if not kid:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")

        public_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                break
        
        if not public_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Clé de signature non trouvée")

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


def get_user_id_from_token(payload: Dict[str, Any]) -> str:
    """Extrait l'ID utilisateur du payload du token."""
    return payload.get("sub")


def get_username_from_token(payload: Dict[str, Any]) -> str:
    """Extrait le nom d'utilisateur du payload du token."""
    return payload.get("preferred_username") or payload.get("name")


def get_email_from_token(payload: Dict[str, Any]) -> str:
    """Extrait l'email du payload du token."""
    return payload.get("email")


def get_roles_from_token(payload: Dict[str, Any]) -> list:
    """Extrait les rôles du payload du token."""
    return payload.get("realm_access", {}).get("roles", [])
