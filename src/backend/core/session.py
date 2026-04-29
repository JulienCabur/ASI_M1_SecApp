"""
Gestion de la session utilisateur via cookie httpOnly signé (BFF).

Le cookie contient les tokens OIDC (access + refresh + expiry). Le payload est
sérialisé JSON puis signé avec itsdangerous (HMAC-SHA256) pour empêcher toute
modification côté navigateur. Aucune donnée n'est lisible côté JS car le cookie
est posé en HttpOnly + Secure + SameSite=Strict.
"""

import json
import os
import time
from typing import Optional

from fastapi import Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

SESSION_COOKIE_NAME = "secuapp_session"
CSRF_COOKIE_NAME = "secuapp_csrf"
OIDC_STATE_COOKIE_NAME = "secuapp_oidc_state"

SESSION_MAX_AGE_SECONDS = 8 * 60 * 60  # 8h
OIDC_STATE_MAX_AGE_SECONDS = 5 * 60    # 5min

_serializer: Optional[URLSafeTimedSerializer] = None


def _get_serializer() -> URLSafeTimedSerializer:
    global _serializer
    if _serializer is None:
        secret = os.getenv("SESSION_SECRET")
        if not secret or len(secret) < 32:
            raise RuntimeError("SESSION_SECRET manquant ou trop court (min 32 caractères)")
        _serializer = URLSafeTimedSerializer(secret, salt="secuapp.session.v1")
    return _serializer


def _cookie_kwargs() -> dict:
    secure = (os.getenv("COOKIE_SECURE", "true").lower() != "false")
    return {
        "httponly": True,
        "secure": secure,
        "samesite": "strict",
        "path": "/",
    }


def encode_session(payload: dict) -> str:
    return _get_serializer().dumps(payload)


def decode_session(token: str, max_age: int = SESSION_MAX_AGE_SECONDS) -> Optional[dict]:
    try:
        return _get_serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


def set_session_cookie(response: Response, payload: dict) -> None:
    token = encode_session(payload)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        **_cookie_kwargs(),
    )


def clear_session_cookie(response: Response) -> None:
    """Supprime tous les cookies posés par le BFF (session, CSRF, état OIDC).
    On force `secure` + `samesite` identiques à la pose pour que le navigateur
    accepte bien le `Set-Cookie` de suppression."""
    secure = (os.getenv("COOKIE_SECURE", "true").lower() != "false")
    for name in (SESSION_COOKIE_NAME, CSRF_COOKIE_NAME, OIDC_STATE_COOKIE_NAME):
        response.delete_cookie(
            key=name,
            path="/",
            secure=secure,
            samesite="strict",
            httponly=(name != CSRF_COOKIE_NAME),
        )


def get_session_payload(request: Request) -> Optional[dict]:
    raw = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw:
        return None
    return decode_session(raw)


def set_oidc_state_cookie(response: Response, payload: dict) -> None:
    token = _get_serializer().dumps(payload)
    response.set_cookie(
        key=OIDC_STATE_COOKIE_NAME,
        value=token,
        max_age=OIDC_STATE_MAX_AGE_SECONDS,
        **_cookie_kwargs(),
    )


def consume_oidc_state_cookie(request: Request, response: Response) -> Optional[dict]:
    raw = request.cookies.get(OIDC_STATE_COOKIE_NAME)
    if not raw:
        return None
    response.delete_cookie(key=OIDC_STATE_COOKIE_NAME, path="/")
    try:
        return _get_serializer().loads(raw, max_age=OIDC_STATE_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None


def set_csrf_cookie(response: Response, token: str) -> None:
    """CSRF en double-submit : ce cookie n'est PAS httpOnly, le JS le lit
    pour le renvoyer dans l'en-tête X-CSRF-Token. La protection vient du fait
    qu'un attaquant cross-site ne peut pas lire ce cookie (SameSite=Strict)."""
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=False,
        secure=(os.getenv("COOKIE_SECURE", "true").lower() != "false"),
        samesite="strict",
        path="/",
    )


def is_session_expired(payload: dict) -> bool:
    exp = payload.get("access_exp")
    if not isinstance(exp, (int, float)):
        return True
    return time.time() >= float(exp) - 5
