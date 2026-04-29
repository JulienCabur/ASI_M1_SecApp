"""Onboarding médecin (CSR / Keycloak / .p12) + challenge cert pour le reset."""

import time
from typing import Any, Dict

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from sqlalchemy.orm import Session

from core.database import get_db
from schema.auth_schema import CertificateRequest, ChallengeResponse
from service.auth_service import AuthService, DoctorConflictError
from service.log_service import LogsService

router = APIRouter()
logs_service = LogsService()


@router.post("/register_doctor", response_model=Dict[str, Any])
async def register_doctor_route(
    user_info: CertificateRequest = Form(...),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    auth_service = AuthService(db=db)
    try:
        # Pré-vérification d'unicité avant d'émettre un certificat PKI : un doublon
        # détecté ici évite une révocation derrière. La création Keycloak revérifie
        # de toute façon (course possible entre deux requêtes simultanées).
        auth_service.check_doctor_uniqueness(user_info.username, user_info.email)
        auth_service.generate_csr(user_info.username, user_info.organization)
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
            "filename": f"{user_info.username}.p12",
        }
    except DoctorConflictError as e:
        # 409 ciblé : la couche présentation préserve `field` pour que le front
        # surligne le bon input (username ou email) sans parser un message libre.
        raise HTTPException(
            status_code=409,
            detail={"message": str(e), "field": e.field},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'enregistrement du médecin: {str(e)}")


@router.get("/challenge", response_model=ChallengeResponse)
async def get_challenge(
    username: str = Query(..., description="Nom d'utilisateur pour lequel générer le challenge"),
    db: Session = Depends(get_db),
) -> ChallengeResponse:
    """Challenge utilisé par le flow de reset par certificat
    (le login par certificat utilise /auth/cert/login/challenge)."""
    auth_service = AuthService(db=db)
    return auth_service.generate_challenge(username)
