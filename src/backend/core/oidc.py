"""
Helpers OIDC pour le flux Authorization Code + PKCE côté backend (BFF).

Toutes les interactions avec Keycloak (génération URL d'autorisation, échange
code <-> tokens, refresh, end-session) sont concentrées ici. Le frontend ne
parle jamais à Keycloak directement.
"""

import base64
import hashlib
import os
import secrets
import time
from typing import Optional, Tuple
from urllib.parse import urlencode

import httpx

from core.auth import resolve_keycloak_verify


def _server_url() -> str:
    url = os.getenv("KEYCLOAK_SERVER_URL")
    if not url:
        raise RuntimeError("KEYCLOAK_SERVER_URL non défini")
    return url.rstrip("/")


def _public_url() -> str:
    return (os.getenv("KEYCLOAK_PUBLIC_URL") or _server_url()).rstrip("/")


def _realm() -> str:
    return os.getenv("KEYCLOAK_REALM", "health_app")


def _client_id() -> str:
    return os.getenv("KEYCLOAK_CLIENT_ID", "health_app_frontend")


def _client_secret() -> str:
    secret = os.getenv("KEYCLOAK_CLIENT_SECRET")
    if not secret:
        raise RuntimeError("KEYCLOAK_CLIENT_SECRET non défini")
    return secret


def _redirect_uri() -> str:
    uri = os.getenv("KEYCLOAK_REDIRECT_URI")
    if not uri:
        raise RuntimeError("KEYCLOAK_REDIRECT_URI non défini")
    return uri


def generate_pkce_pair() -> Tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def build_authorize_url(state: str, code_challenge: str, scope: str = "openid profile email") -> str:
    params = {
        "client_id": _client_id(),
        "response_type": "code",
        "scope": scope,
        "redirect_uri": _redirect_uri(),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{_public_url()}/realms/{_realm()}/protocol/openid-connect/auth?{urlencode(params)}"


def build_logout_url(
    post_logout_redirect_uri: Optional[str] = None,
    id_token_hint: Optional[str] = None,
) -> str:
    """URL que le **navigateur** doit visiter pour clore la session SSO Keycloak.
    Sans `id_token_hint`, Keycloak v18+ affiche un écran de confirmation ;
    avec, le logout est silencieux et le navigateur est redirigé immédiatement."""
    base = f"{_public_url()}/realms/{_realm()}/protocol/openid-connect/logout"
    params: dict = {}
    if id_token_hint:
        params["id_token_hint"] = id_token_hint
    else:
        # Fallback pour les vieilles intégrations qui n'ont pas l'id_token sous la main.
        params["client_id"] = _client_id()
    if post_logout_redirect_uri:
        params["post_logout_redirect_uri"] = post_logout_redirect_uri
    return f"{base}?{urlencode(params)}" if params else base


async def exchange_code_for_tokens(code: str, code_verifier: str) -> dict:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": _redirect_uri(),
        "client_id": _client_id(),
        "client_secret": _client_secret(),
        "code_verifier": code_verifier,
    }
    url = f"{_server_url()}/realms/{_realm()}/protocol/openid-connect/token"
    async with httpx.AsyncClient(verify=resolve_keycloak_verify(), timeout=15.0) as client:
        response = await client.post(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        response.raise_for_status()
        return response.json()


async def refresh_tokens(refresh_token: str) -> dict:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": _client_id(),
        "client_secret": _client_secret(),
    }
    url = f"{_server_url()}/realms/{_realm()}/protocol/openid-connect/token"
    async with httpx.AsyncClient(verify=resolve_keycloak_verify(), timeout=15.0) as client:
        response = await client.post(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        response.raise_for_status()
        return response.json()


async def end_session(refresh_token: str) -> None:
    """Révoque le refresh token côté Keycloak."""
    data = {
        "client_id": _client_id(),
        "client_secret": _client_secret(),
        "refresh_token": refresh_token,
    }
    url = f"{_server_url()}/realms/{_realm()}/protocol/openid-connect/logout"
    async with httpx.AsyncClient(verify=resolve_keycloak_verify(), timeout=15.0) as client:
        try:
            await client.post(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        except httpx.HTTPError:
            # On accepte l'échec silencieux côté serveur : on supprimera quand même le cookie.
            pass


def session_payload_from_token_response(token_response: dict) -> dict:
    """Construit le payload qu'on stocke dans le cookie session."""
    now = int(time.time())
    expires_in = int(token_response.get("expires_in") or 0)
    refresh_expires_in = int(token_response.get("refresh_expires_in") or 0)
    return {
        "access_token": token_response.get("access_token"),
        "refresh_token": token_response.get("refresh_token"),
        "id_token": token_response.get("id_token"),
        "access_exp": now + expires_in,
        "refresh_exp": now + refresh_expires_in if refresh_expires_in else None,
        "issued_at": now,
    }
