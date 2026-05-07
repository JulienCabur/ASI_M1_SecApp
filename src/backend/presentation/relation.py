from fastapi import APIRouter, Depends, HTTPException, Query, Form
from service.relation_service import RelationService
from core.database import get_db
from core.auth import get_current_user

router = APIRouter( # Créer un routeur APIRouter pour les routes de gestion des relations
    prefix="/relation",
    tags=["relation"]
)

@router.post("/patient_add_doctor")
async def patient_add_doctor(
    doctor_id: str = Form(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    try:
        relation_service = RelationService(db=db)
        relation = relation_service.patient_add_doctor(patient_id=current_user.id, doctor_id=doctor_id)

        return {"relations": relation}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la création de la relation: {str(e)}")

@router.post("/patient_remove_doctor")
async def patient_remove_doctor(
    doctor_id: str = Form(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    try:
        relation_service = RelationService(db=db)
        relation_service.delete_relation(patient_id=current_user.id, doctor_id=doctor_id)

        return {"status": "Relations supprimées avec succès"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la suppression de la relation: {str(e)}")

@router.post("/doctor_remove_patient")
async def doctor_remove_patient(
    patient_id: str = Form(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    try:
        relation_service = RelationService(db=db)
        relation_service.delete_relation(patient_id=patient_id, doctor_id=current_user.id)

        return {"status": "Relations supprimées avec succès"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la suppression de la relation: {str(e)}")

@router.get("/get_relations")
async def get_relations(
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    try:
        relation_service = RelationService(db=db)
        relations = relation_service.get_relations(user_id=current_user.id)

        return {"relations": relations}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la récupération des relations: {str(e)}")

@router.post("/doctor_add_patient")
async def doctor_add_patient(
    patient_id: str = Form(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    try:
        relation_service = RelationService(db=db)
        relation = relation_service.doctor_add_patient(doctor_id=current_user.id, patient_id=patient_id)

        return {"relations": relation}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la création de la relation: {str(e)}")

@router.get("/get_unverified_relations")
async def get_unverified_relations(
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    try:
        relation_service = RelationService(db=db)
        relations = relation_service.get_unverified_relations(user_id=current_user.id)

        return {"unverified_relations": relations}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la récupération des relations non vérifiées: {str(e)}")

@router.get
    
@router.post("/patient_verify_doctor")
async def patient_verify_doctor(
    doctor_id: str = Form(...),
    ciphered_kek: str = Form(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    try:
        relation_service = RelationService(db=db)
        relation_id = relation_service.verify_relation(patient_id=current_user.id, doctor_id=doctor_id, ciphered_kek=ciphered_kek)

        return {"status": f"Relation avec l'id {relation_id} vérifiée avec succès"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la vérification de la relation: {str(e)}")

@router.post("/store_kek")
async def store_kek(
    relation_id: str = Form(...),
    ciphered_kek: str = Form(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)):

    try:
        relation_service = RelationService(db=db)
        relation_service.store_kek_for_relation(user_id=current_user.id, relation_id=relation_id, ciphered_kek=ciphered_kek)

        return {"status": "KEK chiffré stocké avec succès pour la relation"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors du stockage du KEK: {str(e)}")

@router.get("/list_doctors")
async def list_doctors(
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    try:
        relation_service = RelationService(db=db)
        doctors = relation_service.list_doctors()

        return {"doctors": doctors}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la récupération des médecins: {str(e)}")

@router.get("/get_patient_kek")
async def get_patient_kek(
    patient_id: str = Query(...),
    device_id: str = Query(...),
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    """
    Renvoie le `ciphered_kek` que le médecin courant peut déballer avec la
    privée RSA de son device, pour ensuite déchiffrer les fichiers du patient.
    """
    try:
        relation_service = RelationService(db=db)
        result = relation_service.get_patient_kek_for_doctor(
            doctor_id=current_user.id,
            doctor_device_id=device_id,
            patient_id=patient_id,
        )
        return result
    except Exception as e:
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
        relation_service = RelationService(db=db)
        patient = relation_service.find_patient_by_username(username=username)

        return {"patient": patient}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"{str(e)}")

# temporary route
@router.get("/create_doctors")
async def create_doctors(
    db = Depends(get_db),
    current_user = Depends(get_current_user)):
    try:
        relation_service = RelationService(db=db)
        relation_service.create_doctors()

        return {"status": "Médecins créés avec succès"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la création des médecins: {str(e)}")

