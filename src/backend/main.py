import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.database import engine, Base
from core.session import CSRF_COOKIE_NAME
from presentation.file import router as file_router
from presentation.auth import router as auth_router
from presentation.check_authenticity import router as check_authenticity_router
from presentation.device import router as key_router
from presentation.events import router as events_router
from service.sse_service import sse_manager

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    sse_manager.set_loop(asyncio.get_event_loop())
    yield


app = FastAPI(
    title="UNamur Medical Institute",
    description="Core API for the UNamur Medical Institute project",
    version="1.0.0",
    root_path="/fastapi",
    lifespan=lifespan,
)

# Avec `allow_credentials=True` les wildcards sont interdits par la spec CORS,
# d'où la liste explicite. À étendre via FRONTEND_URL si besoin.
_allowed_origins = [
    (os.getenv("FRONTEND_URL") or "https://localhost").rstrip("/"),
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    allow_credentials=True,
)


_CSRF_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# Routes BFF qui posent ou consomment le cookie session sans CSRF (le cookie
# n'existe pas encore au login, et le callback est une redirection Keycloak).
_CSRF_EXEMPT_PATHS = {
    "/auth/login",
    "/auth/callback",
}


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double-submit CSRF : pour toute mutation, le client doit envoyer
    l'en-tête `X-CSRF-Token` égal au cookie `secuapp_csrf`. Sans cookie session
    on n'exige rien (la route /auth/login reste appelable depuis le navigateur)."""

    async def dispatch(self, request: Request, call_next):
        if request.method in _CSRF_SAFE_METHODS:
            return await call_next(request)
        if request.url.path in _CSRF_EXEMPT_PATHS:
            return await call_next(request)
        # Dev/testing helper: when enabled, allow skipping CSRF if a Bearer
        # Authorization header is present. This helps testing via the
        # Swagger UI (/fastapi/docs) where adding X-CSRF-Token is awkward.
        # MUST NOT be enabled in production.
        try:
            if os.getenv("DISABLE_CSRF_FOR_BEARER", "false").lower() == "true":
                auth = request.headers.get("Authorization")
                if auth and auth.lower().startswith("bearer "):
                    return await call_next(request)
        except Exception:
            # If anything goes wrong, fall back to normal CSRF enforcement.
            pass
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        if cookie_token:
            header_token = request.headers.get("X-CSRF-Token")
            if not header_token or header_token != cookie_token:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "CSRF token invalide"},
                )
        return await call_next(request)


app.add_middleware(CSRFMiddleware)

app.include_router(file_router)
app.include_router(auth_router)
app.include_router(check_authenticity_router)
app.include_router(key_router)
app.include_router(events_router)


@app.get("/")
def root():
    return {"message": "Welcome to the UNamur Medical Institute API!"}
