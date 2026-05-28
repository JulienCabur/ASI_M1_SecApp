import os
import httpx
import jwt
from typing import Any, Dict, Optional
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer
from schema.auth_schema import UserInDB
from dotenv import load_dotenv
load_dotenv()

security = HTTPBearer(auto_error=False)


def resolve_keycloak_verify() -> bool | str:
    """
    Retourne la valeur de vérification TLS pour Keycloak.
    """
    verify_raw = (os.getenv("KEYCLOAK_VERIFY") or "true").strip()
    ca_bundle = (os.getenv("KEYCLOAK_CA_BUNDLE") or "").strip()

    if ca_bundle:
        return ca_bundle

    verify_lower = verify_raw.lower()
    if verify_lower in {"false", "0", "no", "off"}:
        return False
    if verify_lower in {"true", "1", "yes", "on", ""}:
        return True

    return verify_raw


async def get_keycloak_public_key() -> Dict[str, Any]:
    """
    Récupère la clé publique de Keycloak via son endpoint JWKS (JSON Web Key Set).
    Cette clé est utilisée pour vérifier la signature du JWT.
    """
    try:
        keycloak_url = os.getenv("KEYCLOAK_PUBLIC_KEY_URL")

        async with httpx.AsyncClient(verify=resolve_keycloak_verify()) as client:
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
            audience=os.getenv("KEYCLOAK_CLIENT_ID"),
            options={"verify_aud": True}
        )
        return payload

    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token expiré: {str(e)}")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token invalide: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Erreur lors de la validation du token: {str(e)}")


async def _resolve_access_token(
    request: Request,
    response: Response,
    credentials: Any,
) -> Optional[str]:
    """
    Récupère un access_token valide depuis :
    1. Le cookie session BFF (rafraîchit côté serveur si expiré).
    2. À défaut, l'en-tête Authorization Bearer (compat tests / clients machine).
    """
    from core.session import (
        get_session_payload,
        is_session_expired,
        set_session_cookie,
    )
    from core.oidc import refresh_tokens, session_payload_from_token_response

    payload = get_session_payload(request)
    if payload and payload.get("access_token"):
        if is_session_expired(payload) and payload.get("refresh_token"):
            try:
                token_response = await refresh_tokens(payload["refresh_token"])
                payload = session_payload_from_token_response(token_response)
                set_session_cookie(response, payload)
            except httpx.HTTPError:
                return None
        return payload.get("access_token")

    if credentials and getattr(credentials, "credentials", None):
        return credentials.credentials

    return None


async def get_current_user(
    request: Request,
    response: Response,
    credentials: Any = Depends(security),
) -> UserInDB:
    """
    Dépendance FastAPI pour vérifier l'authentification.
    Lit le token depuis le cookie session BFF en priorité, sinon Authorization Bearer.
    """
    token = await _resolve_access_token(request, response, credentials)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session manquante")

    try:
        public_key = await get_public_key(token)
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=os.getenv("KEYCLOAK_CLIENT_ID"),
            options={"verify_aud": True}
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
