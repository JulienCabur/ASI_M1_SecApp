from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from core.database import get_db
from core.auth import get_current_user
from service.file_service import FileService
from schema.auth_schema import UserInDB
from schema.file_schema import FileBase
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
    log_service.add_logs(action="CREATE_DIRECTORY", log_level="INFO", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
    return {
        "message": f"Répertoire créé pour {str(current_user.id)}",
        "path": directory_path
    }

@router.get("/download_file", response_model=Dict[str, Any])
async def download_file(
    file: str,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    file_service = FileService(db=db, storage_path=os.getenv("STORAGE_PATH"))
    file_data = file_service.save_file(file=file, username=str(current_user.id))
    file_content = file_service.get_base64_file_content(cert_path=file_data.path)
    log_service.add_logs(action="DOWNLOAD_FILE", log_level="INFO", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")

    return {
        "file_content": file_content,
        "key": file_data.ciphered_dek,
        "filename": file_data.name
    }

@router.post("/upload_file", response_model=Dict[str, Any])
async def upload_file(
    file: UploadFile,
    dek: str,
    date: str,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:

    file_service = FileService(db=db, storage_path=os.getenv("STORAGE_PATH"))
    message = file_service.upload_file(file=file, username=str(current_user.id), dek=dek, date=date)
    log_service.add_logs(action="UPLOAD_FILE", log_level="INFO", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
    return {"message": message}

@router.post("/delete_file", response_model=Dict[str, Any])
async def delete_file(
    file: str,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    file_service = FileService(db=db, storage_path=os.getenv("STORAGE_PATH"))
    message = file_service.delete_file(file=file, username=str(current_user.id))
    log_service.add_logs(action="DELETE_FILE", log_level="INFO", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
    return {"message": message}

@router.get("/list_files", response_model=Dict[str, Any])
async def list_files(
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    file_service = FileService(db=db, storage_path=os.getenv("STORAGE_PATH"))
    files = file_service.list_files(username=str(current_user.id))
    log_service.add_logs(action="LIST_FILES", log_level="INFO", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
    return {"files": files}

@router.post("/edit_file", response_model=Dict[str, Any])
async def edit_file(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    file_service = FileService(db=db, storage_path=os.getenv("STORAGE_PATH"))
    message = file_service.edit_file(file=file.filename, new_content=file.file.read(), username=str(current_user.id))
    log_service.add_logs(action="EDIT_FILE", log_level="INFO", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
    return {"message": message}