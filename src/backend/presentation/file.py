import base64
import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from core.database import get_db
from core.auth import get_current_user
from service.file_service import FileService
from schema.auth_schema import UserInDB
from typing import Dict, Any, Optional
from service.log_service import LogsService

router = APIRouter( # Créer un routeur APIRouter pour les routes de gestion des fichiers
    prefix="/files",
    tags=["files"]
)
load_dotenv()
log_service = LogsService("backend_files")

@router.post("/create_directory", response_model=Dict[str, Any])
async def create_directory(
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        if current_user.roles[0] != "role_patients":
            await log_service.add_logs(action="CREATE_DIRECTORY_NOT_ALLOWED", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
            raise HTTPException(status_code=403, detail="Only patients can create their own directory.")

        file_service = FileService(db=db, storage_path=os.getenv("STORAGE_PATH"))
        directory_path = file_service.create_directory_service(username=str(current_user.id))
        await log_service.add_logs(action="CREATE_DIRECTORY", log_level="INFO", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
        return {
            "message": f"Répertoire créé pour {str(current_user.id)}",
            "path": directory_path
        }
    except Exception as e:
        await log_service.add_logs(action="CREATE_DIRECTORY_ERROR", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
        raise HTTPException(status_code=400, detail=f"Erreur lors de la création du répertoire: {str(e)}")

@router.get("/download_file", response_model=Dict[str, Any])
async def download_file(
    file: str,
    patient_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    try:
        if patient_id and current_user.roles[0] != "role_docteurs":
            await log_service.add_logs(action="DOWNLOAD_FILE_NOT_ALLOWED", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
            raise HTTPException(status_code=403, detail="Only doctors can download files from a patient's directory.")

        elif not patient_id and current_user.roles[0] != "role_patients":
            await log_service.add_logs(action="DOWNLOAD_FILE_NOT_ALLOWED", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
            raise HTTPException(status_code=403, detail="Only patients can download files from their own directory.")
        
        if patient_id and current_user.id == patient_id:
            await log_service.add_logs(action="DOWNLOAD_FILE_SELF", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id=patient_id)
            raise HTTPException(status_code=403, detail="Doctors cannot download files from their own directory.")
        
        elif not patient_id and current_user.roles[0] == "role_docteurs":
            await log_service.add_logs(action="DOWNLOAD_FILE_SELF", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
            raise HTTPException(status_code=403, detail="Doctors cannot download files from their own directory.")

        file_service = FileService(db=db, storage_path=os.getenv("STORAGE_PATH"))
        if patient_id:
            file_data = file_service.save_file(file=file, username=patient_id, doctor_id=str(current_user.id))
        else:
            file_data = file_service.save_file(file=file, username=str(current_user.id))
    except Exception as e:
        await log_service.add_logs(action="DOWNLOAD_FILE_ERROR", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id=patient_id if patient_id else "null")
        raise HTTPException(status_code=400, detail=f"Erreur lors du téléchargement du fichier: {str(e)}")
    file_content = file_service.get_base64_file_content(cert_path=file_data.path)
    await log_service.add_logs(action="DOWNLOAD_FILE", log_level="INFO", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")

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
    try:
        if current_user.roles[0] != "role_patients":
            await log_service.add_logs(action="UPLOAD_FILE_NOT_ALLOWED", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
            raise HTTPException(status_code=403, detail="Only patients can upload files to their own directory.")
    
        if len(dek) != 256:
            await log_service.add_logs(action="UPLOAD_FILE_INVALID_DEK", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
            raise HTTPException(status_code=400, detail="DEK must be a base64-encoded JSON envelope (256 characters).")
        try:
            base64.b64decode(dek, validate=True)
        except Exception:
            await log_service.add_logs(action="UPLOAD_FILE_INVALID_DEK", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
            raise HTTPException(status_code=400, detail="DEK n'est pas du base64 valide.")

        file_service = FileService(db=db, storage_path=os.getenv("STORAGE_PATH"))
        message = file_service.upload_file(file=file, username=str(current_user.id), dek=dek, date=date)
        await log_service.add_logs(action="UPLOAD_FILE", log_level="INFO", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
        return {"message": message}
    except Exception as e:
        await log_service.add_logs(action="UPLOAD_FILE_ERROR", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'upload du fichier: {str(e)}")

@router.post("/upload_file_for_doctor", response_model=Dict[str, Any])
async def upload_file_for_doctor(
    file: UploadFile,
    dek: str,
    date: str,
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        if current_user.roles[0] != "role_docteurs":
            await log_service.add_logs(action="UPLOAD_FILE_FOR_DOCTOR_NOT_ALLOWED", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id=patient_id)
            raise HTTPException(status_code=403, detail="Only doctors can upload files to a patient's directory.")
        
        if current_user.id == patient_id:
            await log_service.add_logs(action="UPLOAD_FILE_FOR_DOCTOR_SELF", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id=patient_id)
            raise HTTPException(status_code=400, detail="Doctors cannot upload files to their own directory.")

        if len(dek) != 256:
            await log_service.add_logs(action="UPLOAD_FILE_FOR_DOCTOR_INVALID_DEK", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id=patient_id)
            raise HTTPException(status_code=400, detail="DEK must be a base64-encoded JSON envelope (256 characters).")
        try:
            base64.b64decode(dek, validate=True)
        except Exception:
            await log_service.add_logs(action="UPLOAD_FILE_FOR_DOCTOR_INVALID_DEK", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id=patient_id)
            raise HTTPException(status_code=400, detail="DEK n'est pas du base64 valide.")

        file_service = FileService(db=db, storage_path=os.getenv("STORAGE_PATH"))
        message = file_service.upload_file_for_doctor(file=file, patient_id=patient_id, doctor_id=str(current_user.id), dek=dek, date=date)
        await log_service.add_logs(action="UPLOAD_FILE_FOR_DOCTOR", log_level="INFO", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id=patient_id)
        return {"message": message}
    except Exception as e:
        await log_service.add_logs(action="UPLOAD_FILE_FOR_DOCTOR_ERROR", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id=patient_id)
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'upload du fichier: {str(e)}")

@router.post("/delete_file", response_model=Dict[str, Any])
async def delete_file(
    file: str,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        if current_user.roles[0] != "role_patients":
            await log_service.add_logs(action="DELETE_FILE_NOT_ALLOWED", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
            raise HTTPException(status_code=403, detail="Only patients can delete files from their own directory.")

        file_service = FileService(db=db, storage_path=os.getenv("STORAGE_PATH"))
        message = file_service.delete_file(file=file, username=str(current_user.id))
        await log_service.add_logs(action="DELETE_FILE", log_level="INFO", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
        return {"message": message}
    except Exception as e:
        await log_service.add_logs(action="DELETE_FILE_ERROR", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
        raise HTTPException(status_code=400, detail=f"Erreur lors de la suppression du fichier: {str(e)}")

@router.post("/delete_file_for_doctor", response_model=Dict[str, Any])
async def delete_file_for_doctor(
    file: str = Form(...),
    patient_id: str = Form(...),
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        if current_user.roles[0] != "role_docteurs":
            await log_service.add_logs(action="DELETE_FILE_FOR_DOCTOR_NOT_ALLOWED", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id=patient_id)
            raise HTTPException(status_code=403, detail="Only doctors can delete files from a patient's directory.")

        if current_user.id == patient_id:
            await log_service.add_logs(action="DELETE_FILE_FOR_DOCTOR_SELF", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id=patient_id)
            raise HTTPException(status_code=400, detail="Doctors cannot delete files from their own directory.")

        file_service = FileService(db=db, storage_path=os.getenv("STORAGE_PATH"))
        message = file_service.delete_file_for_doctor(file_name=file, patient_id=patient_id, doctor_id=str(current_user.id))
        await log_service.add_logs(action="DELETE_FILE_FOR_DOCTOR", log_level="INFO", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id=patient_id)
        return {"message": message}
    except Exception as e:
        await log_service.add_logs(action="DELETE_FILE_FOR_DOCTOR_ERROR", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id=patient_id)
        raise HTTPException(status_code=400, detail=f"Erreur lors de la suppression du fichier: {str(e)}")

@router.get("/list_files", response_model=Dict[str, Any])
async def list_files(
    patient_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        if patient_id and current_user.roles[0] != "role_docteurs":
            await log_service.add_logs(action="LIST_FILES_NOT_ALLOWED", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id=patient_id)
            raise HTTPException(status_code=403, detail="Only doctors can list files from a patient's directory.")

        elif not patient_id and current_user.roles[0] != "role_patients":
            await log_service.add_logs(action="LIST_FILES_NOT_ALLOWED", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
            raise HTTPException(status_code=403, detail="Only patients can list files from their own directory.")

        if patient_id and current_user.id == patient_id:
            await log_service.add_logs(action="LIST_FILES_SELF", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id=patient_id)
            raise HTTPException(status_code=403, detail="Doctors cannot list files from their own directory.")

        elif not patient_id and current_user.roles[0] == "role_docteurs":
            await log_service.add_logs(action="LIST_FILES_SELF", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
            raise HTTPException(status_code=403, detail="Doctors cannot list files from their own directory.")

        file_service = FileService(db=db, storage_path=os.getenv("STORAGE_PATH"))
        if patient_id:
            files = file_service.list_files(username=patient_id, doctor_id=str(current_user.id))
        else:
            files = file_service.list_files(username=str(current_user.id))
        await log_service.add_logs(action="LIST_FILES", log_level="INFO", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
    except Exception as e:
        await log_service.add_logs(action="LIST_FILES_ERROR", log_level="ERROR", user_id=str(current_user.id), user_role=current_user.roles[0], patient_id="null")
        raise HTTPException(status_code=400, detail=f"Erreur lors de la liste des fichiers: {str(e)}")
    return {"files": files}
