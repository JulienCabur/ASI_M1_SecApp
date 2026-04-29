"""Helpers partagés par les sous-modules d'auth."""

import os
from typing import Any, Dict

import jwt


def frontend_url() -> str:
    return (os.getenv("FRONTEND_URL") or "https://localhost").rstrip("/")


def decode_token_unverified(token: str) -> Dict[str, Any]:
    """Décodage *non vérifié* uniquement pour extraire des claims d'affichage.
    La vérification sécurité se fait ailleurs (validate_jwt_token / get_current_user)."""
    try:
        return jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
    except Exception:
        return {}
