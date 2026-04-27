"""
Routes d'authentification.

Le frontend ne parle plus directement à Keycloak. Toutes les interactions
OIDC (login, callback, refresh, logout) passent par les routes BFF ci-dessous,
et la session utilisateur est portée par un cookie httpOnly signé.

Routes existantes (register_doctor, challenge, challenge_response) sont
conservées pour le flow d'onboarding médecin par certificat.
"""

import os
import secrets
import time
from typing import Any, Dict
from urllib.parse import urlencode

import httpx
import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Query, Form, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from core.auth import get_current_user, validate_jwt_token
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
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    consume_oidc_state_cookie,
    get_session_payload,
    is_session_expired,
    set_csrf_cookie,
    set_oidc_state_cookie,
    set_session_cookie,
)
from schema.auth_schema import (
    CertificateRequest,
    ChallengeResponse,
    ChallengeResponseRequest,
    PasswordResetRequest,
    UserInDB,
)
from service.auth_service import AuthService
from service.log_service import LogsService

load_dotenv()

router = APIRouter(prefix="/auth", tags=["auth"])
logs_service = LogsService()


def _frontend_url() -> str:
    return (os.getenv("FRONTEND_URL") or "https://localhost").rstrip("/")


def _decode_id_or_access_token_unverified(token: str) -> Dict[str, Any]:
    """Décodage *non vérifié* uniquement pour extraire des claims d'affichage.
    La vérification sécurité se fait ailleurs (validate_jwt_token / get_current_user)."""
    try:
        return jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# BFF — flow OIDC
# ---------------------------------------------------------------------------

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
) -> RedirectResponse:
    """Callback Keycloak : échange le `code` contre des tokens et pose le cookie session."""
    fail_url = f"{_frontend_url()}/login?error=auth_failed"
    if error:
        return RedirectResponse(url=fail_url, status_code=302)

    response = RedirectResponse(url=f"{_frontend_url()}/", status_code=302)
    expected = consume_oidc_state_cookie(request, response)
    if not expected or expected.get("state") != state or not code:
        return RedirectResponse(url=fail_url, status_code=302)

    try:
        token_response = await exchange_code_for_tokens(code, expected["code_verifier"])
    except httpx.HTTPError as exc:
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

    payload = session_payload_from_token_response(token_response)
    set_session_cookie(response, payload)
    set_csrf_cookie(response, secrets.token_urlsafe(32))

    claims = _decode_id_or_access_token_unverified(payload.get("access_token", ""))
    user_sub = claims.get("sub")

    logs_service.add_logs(
        action="LOGIN",
        log_level="INFO",
        user_id=user_sub or "unknown",
        user_role=(claims.get("realm_access", {}).get("roles", ["unknown"]) or ["unknown"])[0],
        patient_id="null",
    )

    redirect_to = expected.get("redirect_to", "/")
    response.headers["location"] = f"{_frontend_url()}{redirect_to}"
    return response


@router.post("/logout")
async def logout_route(request: Request) -> JSONResponse:
    """Logout en deux temps :
      1. Côté backend : révoque le refresh_token via le token-endpoint et efface
         tous nos cookies (`secuapp_session`, `secuapp_csrf`, `secuapp_oidc_state`).
      2. Côté navigateur : on renvoie un `logout_url` que le front doit visiter
         pour que Keycloak supprime ses propres cookies SSO (`KEYCLOAK_IDENTITY`,
         `AUTH_SESSION_ID`...) qui vivent sur le domaine `:8443`, hors de portée
         de notre `Set-Cookie` sur `:443`."""
    payload = get_session_payload(request)
    id_token = payload.get("id_token") if payload else None
    refresh_token = payload.get("refresh_token") if payload else None

    logout_url = build_logout_url(
        post_logout_redirect_uri=f"{_frontend_url()}/login",
        id_token_hint=id_token,
    )
    response = JSONResponse({"status": "logged_out", "logout_url": logout_url})

    if refresh_token:
        await end_session(refresh_token)
        claims = _decode_id_or_access_token_unverified(payload.get("access_token", ""))
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


# ---------------------------------------------------------------------------
# Reset des credentials
# ---------------------------------------------------------------------------

# Rate-limit en mémoire (process-local). Pour du multi-worker, déplacer vers Redis.
_RESET_RATE_LIMIT: Dict[str, list] = {}
_RESET_RATE_LIMIT_WINDOW = 3600  # 1h
_RESET_RATE_LIMIT_MAX = 3


def _check_reset_rate_limit(key: str) -> bool:
    now = time.time()
    history = [t for t in _RESET_RATE_LIMIT.get(key, []) if now - t < _RESET_RATE_LIMIT_WINDOW]
    if len(history) >= _RESET_RATE_LIMIT_MAX:
        _RESET_RATE_LIMIT[key] = history
        return False
    history.append(now)
    _RESET_RATE_LIMIT[key] = history
    return True


@router.post("/reset/request")
async def reset_request_route(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Déclenche l'envoi d'un mail Keycloak `UPDATE_PASSWORD`.
    Réponse uniforme (200) qu'un compte existe ou non, pour empêcher l'énumération."""
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"reset:{client_ip}"
    if not _check_reset_rate_limit(rate_key):
        logs_service.add_logs(
            action="RESET_REQUEST_RATE_LIMITED",
            log_level="WARNING",
            user_id="anonymous",
            user_role="unknown",
            patient_id="null",
        )
        # On répond quand même 200 pour rester non-distinguable.
        return {"status": "ok"}

    auth_service = AuthService(db=db)
    try:
        auth_service.send_credentials_reset_email(payload.email)
        logs_service.add_logs(
            action="RESET_REQUEST_SENT",
            log_level="INFO",
            user_id=payload.email,
            user_role="unknown",
            patient_id="null",
        )
    except Exception as exc:
        # Trace serveur pour debug ; le client reste à 200 pour anti-énumération.
        import traceback
        traceback.print_exc()
        logs_service.add_logs(
            action=f"RESET_REQUEST_FAIL:{type(exc).__name__}:{str(exc)[:200]}",
            log_level="WARNING",
            user_id=payload.email,
            user_role="unknown",
            patient_id="null",
        )
    return {"status": "ok"}


@router.post("/reset/with-certificate")
async def reset_with_certificate_route(
    body: ChallengeResponseRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Reset par certificat médecin : on vérifie la signature du challenge,
    puis Keycloak force un changement de mot de passe à la prochaine connexion."""
    auth_service = AuthService(db=db)
    try:
        auth_service.verify_challenge_response(
            username=body.username,
            nonce=body.nonce,
            timestamp=body.timestamp,
            signature=body.signature,
            certificate=body.certificate,
        )
        auth_service.force_credentials_reset(body.username)
        logs_service.add_logs(
            action="RESET_WITH_CERTIFICATE",
            log_level="INFO",
            user_id=body.username,
            user_role="doctor",
            patient_id="null",
        )
        return {"status": "ok"}
    except Exception as e:
        auth_service.clear_challenge(username=body.username)
        logs_service.add_logs(
            action="RESET_WITH_CERTIFICATE_FAIL",
            log_level="WARNING",
            user_id=body.username,
            user_role="doctor",
            patient_id="null",
        )
        raise HTTPException(status_code=400, detail=f"Échec reset par certificat : {str(e)}")


# ---------------------------------------------------------------------------
# Routes existantes (challenge / register médecin / user info)
# ---------------------------------------------------------------------------

@router.get("/validate_token", response_model=Dict[str, Any])
async def validate_token_route(token: str = Query(..., description="JWT token to validate")) -> Dict[str, Any]:
    try:
        payload = await validate_jwt_token(token)
        logs_service.add_logs(action="VALIDATE_TOKEN", log_level="INFO", user_id=payload.get("sub"), user_role=payload.get("roles", ["unknown"])[0], patient_id="null")
        return {"status": "Token valide", "payload": payload}
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
        p12_password = auth_service.create_doctor_in_keycloak(cert_path, user_info)
        logs_service.add_logs(action="REGISTER_DOCTOR", log_level="INFO", user_id=user_info.username, user_role="doctor", patient_id="null")
        p12_content = auth_service.get_p12_content(cert_path)
        logs_service.add_logs(action="GET_P12_CONTENT", log_level="INFO", user_id=user_info.username, user_role="doctor", patient_id="null")
        auth_service.delete_sensitive_files(user_info.username)
        logs_service.add_logs(action="DELETE_SENSITIVE_FILES", log_level="INFO", user_id=user_info.username, user_role="doctor", patient_id="null")
        return {
            "status": "success",
            "username": user_info.username,
            "certificate_b64": p12_content,
            "password": p12_password,
            "filename": f"{user_info.username}.p12"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'enregistrement du médecin: {str(e)}")


@router.get("/challenge", response_model=ChallengeResponse)
async def get_challenge(
    username: str = Query(..., description="Nom d'utilisateur pour lequel générer le challenge"),
    db: Session = Depends(get_db)) -> ChallengeResponse:
    auth_service = AuthService(db=db)
    return auth_service.generate_challenge(username)


@router.post("/challenge_response", response_model=Dict[str, Any])
async def post_challenge_response(
    ChallengeResponseRequest: ChallengeResponseRequest,
    db: Session = Depends(get_db)) -> Dict[str, Any]:
    auth_service = AuthService(db=db)
    try:
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
