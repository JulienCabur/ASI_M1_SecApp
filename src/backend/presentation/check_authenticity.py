"""Routes publiques permettant de vérifier l'authenticité de la PKI interne
(téléchargement du certificat CA racine et récupération de son empreinte)."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from service.check_authenticity_service import AuthenticityService
from service.log_service import LogsService
import os

router = APIRouter( # Créer un routeur APIRouter pour les routes de gestion des fichiers
    prefix="/check-authenticity",
    tags=["check-authenticity"]
)
logs_service = LogsService("backend_authenticity")
@router.get("/download_ca", response_class=FileResponse)
async def download_file():
    """Télécharge le certificat CA racine de la PKI interne (format PEM)."""
    try:
        authenticity_service = AuthenticityService()
        file_content = authenticity_service.download_ca()
        file = os.path.basename(file_content)
        await logs_service.add_logs(action="DOWNLOAD_CA", log_level="INFO", user_id="null", user_role="null", patient_id="null", message="CA file downloaded successfully")

        return FileResponse(path=file_content, filename=file)
    except Exception as e:
        await logs_service.add_logs(action="DOWNLOAD_CA_ERROR", log_level="ERROR", user_id="null", user_role="null", patient_id="null", message=str(e))
        raise HTTPException(status_code=400, detail=f"Erreur lors du téléchargement du fichier: {str(e)}")
@router.get("/hash_ca")
async def get_hash():
    """Retourne l'empreinte SHA-256 du certificat CA racine pour vérification out-of-band."""
    try:
        authenticity_service = AuthenticityService()
        hash = authenticity_service.get_hash()
        await logs_service.add_logs(action="GET_HASH", log_level="INFO", user_id="null", user_role="null", patient_id="null", message="CA hash retrieved successfully")

        return {"hash": hash}
    except Exception as e:
        await logs_service.add_logs(action="GET_HASH_ERROR", log_level="ERROR", user_id="null", user_role="null", patient_id="null", message=str(e))
        raise HTTPException(status_code=400, detail=f"Erreur lors de la récupération du hash: {str(e)}")