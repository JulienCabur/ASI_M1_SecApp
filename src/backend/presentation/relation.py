"""Routes de gestion des relations patient-médecin : ajout, suppression,
vérification, partage de KEK et gestion des demandes en attente."""

from fastapi import APIRouter, Depends, HTTPException, Query, Form
from service.relation_service import RelationService
from service.log_service import LogsService
from core.database import get_db
from core.auth import get_current_user

router = APIRouter( # Créer un routeur APIRouter pour les routes de gestion des relations
    prefix="/relation",
    tags=["relation"]
)
logs_service = LogsService("backend_relations")

@router.post("/patient_add_doctor")
async def patient_add_doctor(
    doctor_id: str = Form(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    """Permet à un patient d'initier une relation avec un médecin."""
    try:
        if current_user.roles[0] != "role_patients":
            await logs_service.add_logs(action="ADD_DOCTOR_RELATION_FORBIDDEN", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Only patients can add doctors")
            raise HTTPException(status_code=403, detail="Only patients can add doctors.")

        if current_user.id == doctor_id:
            await logs_service.add_logs(action="ADD_DOCTOR_RELATION_SELF", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Patients cannot add themselves as doctors")
            raise HTTPException(status_code=400, detail="Patients cannot add themselves as doctors.")

        relation_service = RelationService(db=db)
        relation = relation_service.patient_add_doctor(patient_id=current_user.id, doctor_id=doctor_id)
        await logs_service.add_logs(action="ADD_DOCTOR_RELATION", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], message="Doctor relation added successfully")
        return {"relations": relation}
    except Exception as e:
        await logs_service.add_logs(action="ADD_DOCTOR_RELATION_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message=str(e))
        raise HTTPException(status_code=400, detail=f"Erreur lors de la création de la relation: {str(e)}")

@router.post("/patient_remove_doctor")
async def patient_remove_doctor(
    doctor_id: str = Form(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    """Permet à un patient de supprimer sa relation avec un médecin."""
    try:
        if current_user.roles[0] != "role_patients":
            await logs_service.add_logs(action="REMOVE_DOCTOR_RELATION_FORBIDDEN", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Only patients can remove doctors")
            raise HTTPException(status_code=403, detail="Only patients can remove doctors.")

        if current_user.id == doctor_id:
            await logs_service.add_logs(action="REMOVE_DOCTOR_RELATION_SELF", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Patients cannot remove themselves as doctors")
            raise HTTPException(status_code=400, detail="Patients cannot remove themselves as doctors.")

        relation_service = RelationService(db=db)
        relation_service.delete_relation(patient_id=current_user.id, doctor_id=doctor_id)
        await logs_service.add_logs(action="REMOVE_DOCTOR_RELATION", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], message="Doctor relation removed successfully")
        return {"status": "Relations supprimées avec succès"}
    except Exception as e:
        await logs_service.add_logs(action="REMOVE_DOCTOR_RELATION_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message=str(e))
        raise HTTPException(status_code=400, detail=f"Erreur lors de la suppression de la relation: {str(e)}")

@router.post("/doctor_remove_patient")
async def doctor_remove_patient(
    patient_id: str = Form(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    """Permet à un médecin de supprimer sa relation avec un patient."""
    try:
        if current_user.roles[0] != "role_docteurs":
            await logs_service.add_logs(action="DOCTOR_REMOVE_PATIENT_FORBIDDEN", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Only doctors can remove patients")
            raise HTTPException(status_code=403, detail="Only doctors can remove patients.")

        if current_user.id == patient_id:
            await logs_service.add_logs(action="DOCTOR_REMOVE_PATIENT_SELF", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Doctors cannot remove themselves as patients")
            raise HTTPException(status_code=400, detail="Doctors cannot remove themselves as patients.")

        relation_service = RelationService(db=db)
        relation_service.delete_relation(patient_id=patient_id, doctor_id=current_user.id)
        await logs_service.add_logs(action="DOCTOR_REMOVE_PATIENT", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], message="Patient relation removed successfully")
        return {"status": "Relations supprimées avec succès"}

    except Exception as e:
        await logs_service.add_logs(action="DOCTOR_REMOVE_PATIENT_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message=str(e))
        raise HTTPException(status_code=400, detail=f"Erreur lors de la suppression de la relation: {str(e)}")

@router.get("/get_relations")
async def get_relations(
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    """Retourne les relations vérifiées de l'utilisateur (patients ou médecins)."""
    try:
        if current_user.roles[0] != "role_patients" and current_user.roles[0] != "role_docteurs":
            await logs_service.add_logs(action="GET_RELATIONS_FORBIDDEN", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Only patients and doctors can view their relations")
            raise HTTPException(status_code=403, detail="Only patients and doctors can view their relations.")

        relation_service = RelationService(db=db)
        relations = relation_service.get_relations(user_id=current_user.id)
        await logs_service.add_logs(action="GET_RELATIONS", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], message="Relations retrieved successfully")

        return {"relations": relations}
    except Exception as e:
        await logs_service.add_logs(action="GET_RELATIONS_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message=str(e))
        raise HTTPException(status_code=400, detail=f"Erreur lors de la récupération des relations: {str(e)}")

@router.post("/doctor_add_patient")
async def doctor_add_patient(
    patient_id: str = Form(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    """Permet à un médecin d'initier une demande de relation avec un patient."""
    try:
        if current_user.roles[0] != "role_docteurs":
            await logs_service.add_logs(action="DOCTOR_ADD_PATIENT_FORBIDDEN", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Only doctors can add patients")
            raise HTTPException(status_code=403, detail="Only doctors can add patients.")

        if current_user.id == patient_id:
            await logs_service.add_logs(action="DOCTOR_ADD_PATIENT_SELF", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Doctors cannot add themselves as patients")
            raise HTTPException(status_code=400, detail="Doctors cannot add themselves as patients.")

        relation_service = RelationService(db=db)
        relation = relation_service.doctor_add_patient(doctor_id=current_user.id, patient_id=patient_id)
        await logs_service.add_logs(action="DOCTOR_ADD_PATIENT", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], message="Patient relation added successfully")
        return {"relations": relation}
    except Exception as e:
        await logs_service.add_logs(action="DOCTOR_ADD_PATIENT_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message=str(e))
        raise HTTPException(status_code=400, detail=f"Erreur lors de la création de la relation: {str(e)}")

@router.get("/get_unverified_relations")
async def get_unverified_relations(
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    """Retourne les relations en attente de vérification de l'utilisateur."""
    try:
        if current_user.roles[0] != "role_patients" and current_user.roles[0] != "role_docteurs":
            await logs_service.add_logs(action="GET_UNVERIFIED_RELATIONS_FORBIDDEN", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Only patients and doctors can view their unverified relations")
            raise HTTPException(status_code=403, detail="Only patients and doctors can view their unverified relations.")
        relation_service = RelationService(db=db)
        relations = relation_service.get_unverified_relations(user_id=current_user.id)
        await logs_service.add_logs(action="GET_UNVERIFIED_RELATIONS", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], message="Unverified relations retrieved successfully")

        return {"unverified_relations": relations}
    except Exception as e:
        await logs_service.add_logs(action="GET_UNVERIFIED_RELATIONS_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message=str(e))
        raise HTTPException(status_code=400, detail=f"Erreur lors de la récupération des relations non vérifiées: {str(e)}")

@router.post("/doctor_cancel_request")
async def doctor_cancel_request(
    request_id: str = Form(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    """Permet à un médecin d'annuler une demande de relation en attente."""
    try:
        if current_user.roles[0] != "role_docteurs":
            await logs_service.add_logs(action="DOCTOR_CANCEL_REQUEST_FORBIDDEN", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Only doctors can cancel their requests")
            raise HTTPException(status_code=403, detail="Only doctors can cancel their requests.")
        relation_service = RelationService(db=db)
        relation_service.cancel_doctor_request(doctor_id=current_user.id, request_id=request_id)
        await logs_service.add_logs(action="DOCTOR_CANCEL_REQUEST", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], message="Doctor request cancelled successfully")
        return {"status": "Demande annulée avec succès"}
    except Exception as e:
        await logs_service.add_logs(action="DOCTOR_CANCEL_REQUEST_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message=str(e))
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'annulation de la demande: {str(e)}")

@router.get("/doctor_pending_requests")
async def doctor_pending_requests(
    patient_id: str = Query(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    """Retourne les demandes de fichiers en attente d'un médecin pour un patient donné."""
    try:
        if current_user.roles[0] != "role_docteurs":
            await logs_service.add_logs(action="DOCTOR_PENDING_REQUESTS_FORBIDDEN", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Only doctors can view their pending requests")
            raise HTTPException(status_code=403, detail="Only doctors can view their pending requests.")

        if current_user.id == patient_id:
            await logs_service.add_logs(action="DOCTOR_PENDING_REQUESTS_SELF", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Doctors cannot view pending requests for themselves")
            raise HTTPException(status_code=400, detail="Doctors cannot view pending requests for themselves.")

        relation_service = RelationService(db=db)
        pending_requests = relation_service.get_doctor_pending_requests(doctor_id=current_user.id, patient_id=patient_id)
        await logs_service.add_logs(action="DOCTOR_PENDING_REQUESTS", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], message="Doctor pending requests retrieved successfully")
        return {"pending_requests": pending_requests}
    except Exception as e:
        await logs_service.add_logs(action="DOCTOR_PENDING_REQUESTS_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message=str(e))
        raise HTTPException(status_code=400, detail=f"Erreur lors de la récupération des demandes en attente du médecin: {str(e)}")

@router.get("/patient_pending_requests")
async def patient_pending_requests(
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    """Retourne les demandes de relation en attente adressées au patient authentifié."""
    try:
        if current_user.roles[0] != "role_patients":
            await logs_service.add_logs(action="PATIENT_PENDING_REQUESTS_FORBIDDEN", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Only patients can view their pending requests")
            raise HTTPException(status_code=403, detail="Only patients can view their pending requests.")
        relation_service = RelationService(db=db)
        pending_requests = relation_service.get_patient_pending_requests(patient_id=current_user.id)
        await logs_service.add_logs(action="PATIENT_PENDING_REQUESTS", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], message="Patient pending requests retrieved successfully")

        return {"pending_requests": pending_requests}
    except Exception as e:
        await logs_service.add_logs(action="PATIENT_PENDING_REQUESTS_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message=str(e))
        raise HTTPException(status_code=400, detail=f"Erreur lors de la récupération des demandes en attente du patient: {str(e)}")

@router.post("/patient_validate_request")
async def patient_validate_request(
    request_id: str = Form(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    """Permet au patient de valider une demande de relation soumise par un médecin."""
    try:
        if current_user.roles[0] != "role_patients":
            await logs_service.add_logs(action="PATIENT_VALIDATE_REQUEST_FORBIDDEN", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Only patients can validate requests")
            raise HTTPException(status_code=403, detail="Only patients can validate requests.")
        relation_service = RelationService(db=db)
        relation_service.validate_patient_request(patient_id=current_user.id, request_id=request_id)
        await logs_service.add_logs(action="VALIDATE_RELATION_REQUEST", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], message="Relation request validated successfully")
        return {"status": "Demande validée avec succès"}
    except Exception as e:
        await logs_service.add_logs(action="PATIENT_VALIDATE_REQUEST_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message=str(e))
        raise HTTPException(status_code=400, detail=f"Erreur lors de la validation de la demande: {str(e)}")

@router.post("/patient_reject_request")
async def patient_reject_request(
    request_id: str = Form(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    """Permet au patient de rejeter une demande de relation soumise par un médecin."""
    try:
        if current_user.roles[0] != "role_patients":
            await logs_service.add_logs(action="PATIENT_REJECT_REQUEST_FORBIDDEN", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Only patients can reject requests")
            raise HTTPException(status_code=403, detail="Only patients can reject requests.")
        relation_service = RelationService(db=db)
        relation_service.reject_patient_request(patient_id=current_user.id, request_id=request_id)
        await logs_service.add_logs(action="REJECT_RELATION_REQUEST", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], message="Relation request rejected successfully")
        return {"status": "Demande rejetée avec succès"}
    except Exception as e:
        await logs_service.add_logs(action="PATIENT_REJECT_REQUEST_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message=str(e))
        raise HTTPException(status_code=400, detail=f"Erreur lors du rejet de la demande: {str(e)}")

@router.post("/patient_verify_doctor")
async def patient_verify_doctor(
    doctor_id: str = Form(...),
    ciphered_kek: str = Form(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    """Vérifie la relation avec un médecin et stocke la KEK chiffrée pour lui."""
    try:
        if current_user.roles[0] != "role_patients":
            await logs_service.add_logs(action="PATIENT_VERIFY_DOCTOR_FORBIDDEN", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Only patients can verify doctors")
            raise HTTPException(status_code=403, detail="Only patients can verify doctors.")

        if current_user.id == doctor_id:
            await logs_service.add_logs(action="PATIENT_VERIFY_DOCTOR_SELF", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Patients cannot verify themselves as doctors")
            raise HTTPException(status_code=400, detail="Patients cannot verify themselves as doctors.")

        relation_service = RelationService(db=db)
        relation_id = relation_service.verify_relation(patient_id=current_user.id, doctor_id=doctor_id, ciphered_kek=ciphered_kek)
        await logs_service.add_logs(action="VERIFY_DOCTOR_RELATION", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], message="Doctor relation verified successfully")
        return {"status": f"Relation avec l'id {relation_id} vérifiée avec succès"}
    except Exception as e:
        await logs_service.add_logs(action="PATIENT_VERIFY_DOCTOR_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message=str(e))
        raise HTTPException(status_code=400, detail=f"Erreur lors de la vérification de la relation: {str(e)}")

@router.post("/store_kek")
async def store_kek(
    relation_id: str = Form(...),
    ciphered_kek: str = Form(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    """Stocke le KEK chiffré d'un patient pour une relation donnée."""
    try:
        if current_user.roles[0] != "role_patients":
            await logs_service.add_logs(action="PATIENT_STORE_KEK_FORBIDDEN", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Only patients can store KEKs")
            raise HTTPException(status_code=403, detail="Only patients can store KEKs.")

        if len(ciphered_kek) != 684:
            await logs_service.add_logs(action="PATIENT_STORE_KEK_INVALID", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="KEK must be a 684-character base64-encoded RSA-OAEP wrapped AES-256 key")
            raise HTTPException(status_code=400, detail="KEK must be a base64-encoded RSA-OAEP wrapped AES-256 key (684 characters).")

        relation_service = RelationService(db=db)
        relation_service.store_kek_for_relation(user_id=current_user.id, relation_id=relation_id, ciphered_kek=ciphered_kek)
        await logs_service.add_logs(action="STORE_KEK_RELATION", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], message="KEK stored successfully for relation")
        return {"status": "KEK chiffré stocké avec succès pour la relation"}

    except Exception as e:
        await logs_service.add_logs(action="PATIENT_STORE_KEK_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message=str(e))
        raise HTTPException(status_code=400, detail=f"Erreur lors du stockage du KEK: {str(e)}")

@router.get("/list_doctors")
async def list_doctors(
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    """Retourne la liste de tous les médecins disponibles (accessible aux patients)."""
    try:
        if current_user.roles[0] != "role_patients":
            await logs_service.add_logs(action="LIST_DOCTORS_FORBIDDEN", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Only patients can list doctors")
            raise HTTPException(status_code=403, detail="Only patients can list doctors.")
        relation_service = RelationService(db=db)
        doctors = relation_service.list_doctors()
        await logs_service.add_logs(action="LIST_DOCTORS", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], message="Doctors listed successfully")

        return {"doctors": doctors}
    except Exception as e:
        await logs_service.add_logs(action="LIST_DOCTORS_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message=str(e))
        raise HTTPException(status_code=400, detail=f"Erreur lors de la récupération des médecins: {str(e)}")

@router.get("/get_patient_kek")
async def get_patient_kek(
    patient_id: str = Query(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    """
    Renvoie le `ciphered_kek` patient que le médecin courant peut déballer
    avec sa privée MEK (en mémoire de session), pour ensuite déchiffrer les
    fichiers du patient.
    """
    try:
        if current_user.roles[0] != "role_docteurs":
            await logs_service.add_logs(action="GET_PATIENT_KEK_FORBIDDEN", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Only doctors can get patient KEKs")
            raise HTTPException(status_code=403, detail="Only doctors can get patient KEKs.")
        if current_user.id == patient_id:
            await logs_service.add_logs(action="GET_PATIENT_KEK_SELF", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Doctors cannot get their own patient KEK")
            raise HTTPException(status_code=400, detail="Doctors cannot get their own patient KEK.")
        relation_service = RelationService(db=db)
        result = relation_service.get_patient_kek_for_doctor(
            doctor_id=current_user.id,
            patient_id=patient_id,
        )
        await logs_service.add_logs(action="GET_PATIENT_KEK", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], message="Patient KEK retrieved successfully")
        return result
    except Exception as e:
        await logs_service.add_logs(action="GET_PATIENT_KEK_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message=str(e))
        raise HTTPException(status_code=400, detail=f"Erreur lors de la récupération de la KEK patient: {str(e)}")

@router.get("/find_patient")
async def find_patient(
    username: str = Query(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    """
    Recherche un patient par username exact (utilisé côté médecin pour ajouter
    un patient sans avoir à connaître son UUID). Match strict — pas de
    listing global pour éviter l'énumération.
    """
    try:
        if current_user.roles[0] != "role_docteurs":
            await logs_service.add_logs(action="FIND_PATIENT_FORBIDDEN", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Only doctors can find patients")
            raise HTTPException(status_code=403, detail="Only doctors can find patients.")

        if current_user.username == username:
            await logs_service.add_logs(action="FIND_PATIENT_SELF", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message="Doctors cannot find themselves as patients")
            raise HTTPException(status_code=400, detail="Doctors cannot find themselves as patients.")

        relation_service = RelationService(db=db)
        patient = relation_service.find_patient_by_username(username=username)
        await logs_service.add_logs(action="FIND_PATIENT", log_level="INFO", user_id=current_user.id, user_role=current_user.roles[0], message="Patient found successfully")
        return {"patient": patient}
    except Exception as e:
        await logs_service.add_logs(action="FIND_PATIENT_ERROR", log_level="ERROR", user_id=current_user.id, user_role=current_user.roles[0], message=str(e))
        raise HTTPException(status_code=404, detail=f"{str(e)}")
