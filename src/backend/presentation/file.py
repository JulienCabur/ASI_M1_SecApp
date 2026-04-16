from fastapi import APIRouter, Depends, UploadFile, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from core.database import get_db
from core.auth import get_current_user, validate_jwt_token
from service.file_service import FileService
from schema.auth_schema import UserInDB
from typing import Dict, Any
from service.log_service import LogsService
import os

router = APIRouter( # Créer un routeur APIRouter pour les routes de gestion des fichiers
    prefix="/files",
    tags=["files"]
)
load_dotenv()
log_service = LogsService()

@router.post("/create_directory", response_model=Dict[str, Any])
async def create_directory(
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:

    file_service = FileService(db=db, storage_path=os.getenv("STORAGE_PATH"))
    directory_path = file_service.create_directory_service(username=str(current_user.id))
    log_service.add_logs([f"Directory created for user {current_user.id} at path: {directory_path}"], category="INFO", log_type="api")
    return {
        "message": f"Répertoire créé pour {str(current_user.id)}",
        "path": directory_path
    }

@router.get("/download_file", response_class=FileResponse)
async def download_file(
    file: str,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    storage_path = os.getenv("STORAGE_PATH")

    file_service = FileService(db=db, storage_path=storage_path)
    file_content = file_service.save_file(file=file, username=str(current_user.id))
    log_service.add_logs([f"File downloaded by user {current_user.id}: {file}"], category="INFO", log_type="api")

    return FileResponse(path=file_content, filename=file)

@router.post("/upload_file", response_model=Dict[str, Any])
async def upload_file(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:

    file_service = FileService(db=db, storage_path=os.getenv("STORAGE_PATH"))
    message = file_service.upload_file(file=file, username=str(current_user.id))
    log_service.add_logs([f"File uploaded by user {current_user.id}: {file.filename}"], category="INFO", log_type="api")
    return {"message": message}