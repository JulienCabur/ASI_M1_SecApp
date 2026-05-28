import os

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from datetime import datetime

from core.database import engine, Base
from core.session import CSRF_COOKIE_NAME
from service.log_service import LogsService
from service.metadata_service import MetadataService
from schema.metadata_schema import MetadataBase
from presentation.file import router as file_router
from presentation.auth import router as auth_router
from presentation.check_authenticity import router as check_authenticity_router
from presentation.device import router as key_router
from presentation.relation import router as relation_router

Base.metadata.create_all(bind=engine)

logs_service = LogsService()
_metadata_logs = LogsService("backend_metadata")

app = FastAPI(
    title="UNamur Medical Institute",
    description="Core API for the UNamur Medical Institute project",
    version="1.0.0",
    root_path="/fastapi",
)

_allowed_origins = [
    (os.getenv("FRONTEND_URL") or "https://localhost").rstrip("/"),
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-Timestamp"],
    allow_credentials=True,
)

ROUTE_PRIVILEGES = {
    "/files/create_directory": "role_patients",
    "/files/upload_file": "role_patients",
    "/files/upload_file_for_doctor": "role_docteurs",
    "/files/download_file": "role_patients|role_docteurs",
    "/files/delete_file": "role_patients",
    "/files/delete_file_for_doctor": "role_docteurs",
    "/files/list_files": "role_patients|role_docteurs",
    "/keys/register_device": "authenticated",
    "/keys/store_kek": "authenticated",
    "/keys/get_device_keys": "authenticated",
    "/keys/list_unverified_devices": "authenticated",
    "/keys/list_verified_devices": "authenticated",
    "/keys/verify_device": "authenticated",
    "/keys/reject_device": "authenticated",
    "/keys/revoke_device": "authenticated",
    "/relation/patient_add_doctor": "role_patients",
    "/relation/patient_remove_doctor": "role_patients",
    "/relation/patient_verify_doctor": "role_patients",
    "/relation/store_kek": "role_patients",
    "/relation/doctor_add_patient": "role_docteurs",
    "/relation/doctor_remove_patient": "role_docteurs",
    "/relation/get_relations": "role_patients|role_docteurs",
    "/relation/get_unverified_relations": "role_patients|role_docteurs",
    "/relation/get_patient_kek": "role_docteurs",
    "/relation/patient_pending_requests": "role_patients",
    "/relation/doctor_pending_requests": "role_docteurs",
    "/relation/patient_validate_request": "role_patients",
    "/relation/patient_reject_request": "role_patients",
    "/relation/doctor_cancel_request": "role_docteurs",
    "/auth/login": "unauthenticated",
    "/auth/callback": "unauthenticated",
}


class MetadataMiddleware(BaseHTTPMiddleware):
    """Vérifie les métadonnées structurelles de chaque requête pour détecter
    des anomalies (décalage horaire, taille anormale) sans accéder au contenu."""

    async def dispatch(self, request: Request, call_next):
        timestamp_str = request.headers.get("X-Request-Timestamp")
        if timestamp_str:
            try:
                client_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                path = request.url.path
                size_data = int(request.headers.get("content-length", "0"))
                tree_depth = len([p for p in path.split("/") if p])
                privilege = ROUTE_PRIVILEGES.get(path, "authenticated")

                metadata = MetadataBase(time=client_time,size_data=size_data,privilege_need=privilege,tree_depth=tree_depth,method=request.method)
                svc = MetadataService(db=None)
                is_anomaly, reasons = svc.verify_metadata(metadata)
                if is_anomaly:
                    for reason in reasons:
                        await _metadata_logs.add_logs(
                            action=f"METADATA_ANOMALY_{reason[:40].upper().replace(' ', '_')}",
                            log_level="WARNING",
                            user_id="unknown",
                            user_role="unknown",
                            patient_id="null",
                            message=reason,
                        )
            except Exception as e:
                await _metadata_logs.add_logs(
                    action="METADATA_PROCESSING_ERROR",
                    log_level="ERROR",
                    user_id="unknown",
                    user_role="unknown",
                    patient_id="null",
                    message=str(e),
                )

        return await call_next(request)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double-submit CSRF : pour toute mutation, le client doit envoyer
    l'en-tête `X-CSRF-Token` égal au cookie `secuapp_csrf`. Sans cookie session
    on n'exige rien (la route /auth/login reste appelable depuis le navigateur)."""

    async def dispatch(self, request: Request, call_next):
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return await call_next(request)
        if request.url.path in {"/auth/login","/auth/callback"}:
            return await call_next(request)
        try:
            if os.getenv("DISABLE_CSRF_FOR_BEARER", "false").lower() == "true":
                auth = request.headers.get("Authorization")
                if auth and auth.lower().startswith("bearer "):
                    return await call_next(request)
        except Exception:
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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; object-src 'none';"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(MetadataMiddleware)

app.include_router(file_router)
app.include_router(auth_router)
app.include_router(check_authenticity_router)
app.include_router(key_router)
app.include_router(relation_router)

@app.get("/")
def root():
    return {"message": "Welcome to the UNamur Medical Institute API!"}
