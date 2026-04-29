"""Flux OIDC BFF : login, callback, logout, refresh, me.

Le frontend ne parle jamais directement à Keycloak ; tout passe par ces
routes et la session utilisateur est portée par un cookie httpOnly signé.
"""

import secrets
from typing import Any, Dict

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from core.auth import validate_jwt_token
from core.database import get_db
from core.oidc import (
    build_authorize_url,
    build_logout_url,
    end_session,
    exchange_code_for_tokens,
    generate_pkce_pair,
    refresh_tokens,
    session_payload_from_token_response,
)
from core.session import (
    clear_session_cookie,
    consume_oidc_state_cookie,
    get_session_payload,
    is_session_expired,
    set_csrf_cookie,
    set_oidc_state_cookie,
    set_session_cookie,
)
from service.auth_service import AuthService
from service.log_service import LogsService

from ._helpers import decode_token_unverified, frontend_url

router = APIRouter()
logs_service = LogsService()


@router.get("/login")
async def login_route(request: Request, redirect_to: str = Query(default="/")) -> RedirectResponse:
    """Démarre le flux Authorization Code + PKCE.
    On dépose un cookie temporaire signé contenant `state` et `code_verifier`
    pour les vérifier au callback. `redirect_to` permet à l'app front de
    revenir sur la page initialement demandée après login."""
    state = secrets.token_urlsafe(32)
    verifier, challenge = generate_pkce_pair()
    authorize_url = build_authorize_url(state=state, code_challenge=challenge)
    response = RedirectResponse(url=authorize_url, status_code=302)
    set_oidc_state_cookie(
        response,
        {
            "state": state,
            "code_verifier": verifier,
            "redirect_to": redirect_to if redirect_to.startswith("/") else "/",
        },
    )
    return response


@router.get("/callback")
async def callback_route(
    request: Request,
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str = Query(default=""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Callback Keycloak : échange le `code` contre des tokens et pose le cookie session."""
    fail_url = f"{frontend_url()}/login?error=auth_failed"
    if error:
        return RedirectResponse(url=fail_url, status_code=302)

    response = RedirectResponse(url=f"{frontend_url()}/", status_code=302)
    expected = consume_oidc_state_cookie(request, response)
    if not expected or expected.get("state") != state or not code:
        return RedirectResponse(url=fail_url, status_code=302)

    try:
        token_response = await exchange_code_for_tokens(code, expected["code_verifier"])
    except httpx.HTTPError:
        logs_service.add_logs(
            action="OIDC_CALLBACK_FAIL",
            log_level="WARNING",
            user_id="anonymous",
            user_role="unknown",
            patient_id="null",
        )
        return RedirectResponse(url=fail_url, status_code=302)

    try:
        await validate_jwt_token(token_response.get("access_token", ""))
    except HTTPException:
        return RedirectResponse(url=fail_url, status_code=302)

    claims = decode_token_unverified(token_response.get("access_token", ""))
    user_sub = claims.get("sub")
    user_role = (claims.get("realm_access", {}).get("roles", ["unknown"]) or ["unknown"])[0]

    expected_cert_username = expected.get("cert_proven_username")
    if expected_cert_username:
        actual_username = claims.get("preferred_username")
        if not actual_username or actual_username != expected_cert_username:
            logs_service.add_logs(
                action="CERT_BINDING_MISMATCH",
                log_level="WARNING",
                user_id=actual_username or "unknown",
                user_role=user_role,
                patient_id="null",
            )
            return RedirectResponse(url=fail_url, status_code=302)

    # Cleanup post-reset : si l'utilisateur vient de finir le flow d'action
    # email (CONFIGURE_TOTP + webauthn-register-passwordless), il a un nouveau
    # TOTP/passkey *en plus* des anciens. On garde le plus récent de chaque
    # type et on supprime les autres. Hors flow de reset c'est un no-op
    # (un seul credential par type). Une exception ici ne doit pas casser
    # le login : sera retenté à la prochaine connexion.
    if user_sub:
        try:
            AuthService(db=db).cleanup_stale_credentials(user_sub)
        except Exception:
            logs_service.add_logs(
                action="CRED_CLEANUP_FAIL",
                log_level="WARNING",
                user_id=user_sub,
                user_role=user_role,
                patient_id="null",
            )

    payload = session_payload_from_token_response(token_response)
    set_session_cookie(response, payload)
    set_csrf_cookie(response, secrets.token_urlsafe(32))

    logs_service.add_logs(
        action="LOGIN",
        log_level="INFO",
        user_id=user_sub or "unknown",
        user_role=user_role,
        patient_id="null",
    )

    redirect_to = expected.get("redirect_to", "/")
    response.headers["location"] = f"{frontend_url()}{redirect_to}"
    return response


@router.post("/logout")
async def logout_route(request: Request) -> JSONResponse:
    payload = get_session_payload(request)
    id_token = payload.get("id_token") if payload else None
    refresh_token = payload.get("refresh_token") if payload else None

    logout_url = build_logout_url(
        post_logout_redirect_uri=f"{frontend_url()}/login",
        id_token_hint=id_token,
    )
    response = JSONResponse({"status": "logged_out", "logout_url": logout_url})

    if refresh_token:
        await end_session(refresh_token)
        claims = decode_token_unverified(payload.get("access_token", ""))
        logs_service.add_logs(
            action="LOGOUT",
            log_level="INFO",
            user_id=claims.get("sub", "unknown"),
            user_role=(claims.get("realm_access", {}).get("roles", ["unknown"]) or ["unknown"])[0],
            patient_id="null",
        )
    clear_session_cookie(response)
    return response


@router.post("/refresh")
async def refresh_route(request: Request) -> JSONResponse:
    """Force un refresh côté serveur (le front n'a aucun token, il appelle juste /refresh)."""
    payload = get_session_payload(request)
    if not payload or not payload.get("refresh_token"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Pas de session")
    try:
        token_response = await refresh_tokens(payload["refresh_token"])
    except httpx.HTTPError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh impossible")
    new_payload = session_payload_from_token_response(token_response)
    response = JSONResponse({"status": "refreshed", "expires_at": new_payload["access_exp"]})
    set_session_cookie(response, new_payload)
    return response


@router.get("/me")
async def me_route(request: Request, response: Response) -> Dict[str, Any]:
    """Retourne le profil utilisateur lu depuis le cookie session.
    Réponse 401 (et pas de body) si la session est invalide ou expirée."""
    payload = get_session_payload(request)
    if not payload or not payload.get("access_token"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Non authentifié")

    if is_session_expired(payload) and payload.get("refresh_token"):
        try:
            token_response = await refresh_tokens(payload["refresh_token"])
            payload = session_payload_from_token_response(token_response)
            set_session_cookie(response, payload)
        except httpx.HTTPError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expirée")

    try:
        claims = await validate_jwt_token(payload["access_token"])
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")

    return {
        "id": claims.get("sub"),
        "username": claims.get("preferred_username") or claims.get("name"),
        "email": claims.get("email", ""),
        "first_name": claims.get("given_name", ""),
        "last_name": claims.get("family_name", ""),
        "roles": claims.get("realm_access", {}).get("roles", []),
    }
