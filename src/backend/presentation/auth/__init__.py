"""Routes d'authentification.

Le frontend ne parle plus directement à Keycloak. Toutes les interactions
OIDC (login, callback, refresh, logout) passent par les routes BFF de ce
package, et la session utilisateur est portée par un cookie httpOnly signé.

Sous-modules :
- oidc       : flux OIDC standard (/login, /callback, /logout, /refresh, /me)
- cert_login : login médecin par certificat (/cert/login/...)
- reset      : reset des credentials (/reset/request, /reset/with-certificate)
- doctor     : onboarding médecin + challenge cert pour le reset
"""

from fastapi import APIRouter

from . import cert_login, doctor, oidc, reset

router = APIRouter(prefix="/auth", tags=["auth"])
router.include_router(oidc.router)
router.include_router(cert_login.router)
router.include_router(reset.router)
router.include_router(doctor.router)
