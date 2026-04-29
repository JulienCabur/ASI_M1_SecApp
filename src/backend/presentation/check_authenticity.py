from fastapi import APIRouter
from fastapi.responses import FileResponse
from service.check_authenticity_service import AuthenticityService
import os

router = APIRouter( # Créer un routeur APIRouter pour les routes de gestion des fichiers
    prefix="/check-authenticity",
    tags=["check-authenticity"]
)

@router.get("/download_ca", response_class=FileResponse)
async def download_file():

    authenticity_service = AuthenticityService()
    file_content = authenticity_service.download_ca()
    file = os.path.basename(file_content)

    return FileResponse(path=file_content, filename=file)

@router.get("/hash_ca")
async def get_hash():

    authenticity_service = AuthenticityService()
    hash = authenticity_service.get_hash()

    return {"hash": hash}