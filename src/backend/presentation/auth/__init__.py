"""Routes d'authentification.

Le frontend ne parle plus directement à Keycloak. Toutes les interactions
OIDC (login, callback, refresh, logout) passent par les routes BFF de ce
package, et la session utilisateur est portée par un cookie httpOnly signé.

Sous-modules :
- oidc       : flux OIDC standard (/login, /callback, /logout, /refresh, /me)
- cert : login médecin par certificat (/cert/login/...)
- reset      : reset des credentials (/reset/request, /reset/with-certificate)
"""

from fastapi import APIRouter

from . import cert, oidc, reset

router = APIRouter(prefix="/auth", tags=["auth"])
router.include_router(oidc.router)
router.include_router(cert.router)
router.include_router(reset.router)
