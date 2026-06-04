"""Routes d'authentification.
"""

from fastapi import APIRouter
from . import account, cert, oidc, reset, security_event

router = APIRouter(prefix="/auth", tags=["auth"])
router.include_router(oidc.router)
router.include_router(cert.router)
router.include_router(reset.router)
router.include_router(security_event.router)
router.include_router(account.router)
