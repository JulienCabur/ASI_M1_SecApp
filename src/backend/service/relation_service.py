import os
import shutil

from service.file_service import FileService
from models.file import File

from models.relation import Relation
from models.user import User
from models.devices import Device
from models.file_requests import FileOperationRequest
from schema.file_requests_schema import OperationType, RequestStatus
from schema.relation_schema import RelationBase, RelationResponse, RelationDoctorResponse
class RelationService:
    """
    Classe pour gérer les opérations liées aux fichiers.
    """
    def __init__(self, db):
        """
        Initialise le service de gestion des fichiers avec une session de base de données et un chemin de stockage.
        :param db: Session de base de données SQLAlchemy.
        :param storage_path: Chemin du répertoire de stockage des fichiers.
        """
        self.db = db
    
    def patient_add_doctor(self, patient_id: str, doctor_id: str) -> RelationResponse:
        """
        Crée une relation entre un patient et un médecin.
        :param patient_id: ID du patient.
        :param doctor_id: ID du médecin.
        """
        patient = self.db.query(User).filter(User.id == patient_id, User.roles == "patient").first()
        if not patient:
            raise ValueError(f"Le patient avec l'ID '{patient_id}' n'existe pas ou n'est pas un patient.")

        doctor = self.db.query(User).filter(User.id == doctor_id, User.roles == "doctor").first()
        if not doctor:
            raise ValueError(f"Le médecin avec l'ID '{doctor_id}' n'existe pas ou n'est pas un médecin.")

        if not doctor.public_mek:
            raise ValueError(f"Le médecin avec l'ID '{doctor_id}' n'a pas de dispositif vérifié.")

        relation = Relation(patient_id=patient_id, doctor_id=doctor_id, is_verified=True)
        self.db.add(relation)
        self.db.commit()
        self.db.refresh(relation)
        
        final_relation = RelationBase(
            relation_id=relation.id,
            public_key=doctor.public_mek,
        )

        return RelationResponse(relation=[final_relation])

    def get_doctor_pending_requests(self, doctor_id: str, patient_id: str):
        """
        Récupère les demandes de fichiers en attente initiées par un médecin pour un patient donné.
        """
        relation = self.db.query(Relation).filter(
            Relation.doctor_id == doctor_id,
            Relation.patient_id == patient_id,
            Relation.is_verified.is_(True)
        ).first()
        if not relation:
            return []
        return [
            {
                "relation_id": req.relation_id,
                "doctor_id": doctor_id,
                "file_request_id": req.id,
                "operation_type": req.operation_type,
                "file_name": req.file_name,
                "date": req.date,
                "ciphered_dek": req.ciphered_dek,
            }
            for req in self.db.query(FileOperationRequest).filter(
                FileOperationRequest.relation_id == relation.id,
                FileOperationRequest.status == RequestStatus.PENDING,
            ).all()
        ]

    def cancel_doctor_request(self, doctor_id: str, request_id: str):
        """
        Annule une demande de fichier initiée par un médecin.
        Pour les opérations CREATE, supprime aussi le fichier temporaire.
        """
        file_request = self.db.query(FileOperationRequest).filter(
            FileOperationRequest.id == request_id
        ).first()
        if not file_request:
            raise ValueError(f"Demande introuvable : {request_id}")
        relation = self.db.query(Relation).filter(
            Relation.id == file_request.relation_id,
            Relation.doctor_id == doctor_id,
        ).first()
        if not relation:
            raise ValueError("Non autorisé à annuler cette demande.")
        if file_request.operation_type == OperationType.CREATE:
            temp_path = os.path.join(
                "/temp_storage",
                str(relation.patient_id),
                file_request.file_name,
            )
            if os.path.exists(temp_path):
                os.remove(temp_path)
        self.db.delete(file_request)
        self.db.commit()

    def get_patient_pending_requests(self, patient_id: str):
        """
        Récupère les demandes de relation en attente pour un patient donné.
        :param patient_id: ID du patient.
        :return: Liste des demandes de relation en attente.
        """
        relations = self.db.query(Relation).filter(Relation.patient_id == patient_id, Relation.is_verified.is_(True)).all()
        pending_requests = []
        for relation in relations:
            file_requests = self.db.query(FileOperationRequest).filter(FileOperationRequest.relation_id == relation.id, FileOperationRequest.status == RequestStatus.PENDING).all()
            for file_request in file_requests:
                pending_requests.append({
                    "relation_id": relation.id,
                    "doctor_id": relation.doctor_id,
                    "file_request_id": file_request.id,
                    "operation_type": file_request.operation_type,
                    "file_name": file_request.file_name,
                    "date": file_request.date,
                    "ciphered_dek": file_request.ciphered_dek
                })
        return pending_requests

    def validate_patient_request(self, patient_id: str, request_id: str):
        """
        Valide une demande de relation pour un patient donné.
        :param patient_id: ID du patient.
        :param request_id: ID de la demande de relation à valider.
        """
        file_request = self.db.query(FileOperationRequest).filter(FileOperationRequest.id == request_id).first()
        if not file_request:
            raise ValueError(f"Aucune demande de relation trouvée avec l'ID '{request_id}'.")

        relation = self.db.query(Relation).filter(Relation.id == file_request.relation_id, Relation.patient_id == patient_id).first()
        if not relation:
            raise ValueError(f"Aucune relation trouvée pour le patient '{patient_id}' avec la demande '{request_id}'.")
        
        file_service = FileService(db=self.db, storage_path=os.getenv("STORAGE_PATH"))

        match file_request.operation_type:
            case OperationType.CREATE:
                try:
                    shutil.move(os.path.join(file_service.temp_storage_path, patient_id, file_request.file_name), os.path.join(file_service.storage_path, patient_id, file_request.file_name))
                    file_record = File(name=file_request.file_name, date=file_request.date, user_id=patient_id, ciphered_dek=file_request.ciphered_dek)
                    self.db.add(file_record)
                    self.db.commit()
                except Exception as e:
                    raise ValueError(f"Erreur lors du déplacement du fichier: {str(e)}")
            case OperationType.UPDATE:
                try:
                    file_record = self.db.query(File).filter(File.name == file_request.file_name, File.user_id == patient_id).first()
                    if not file_record:
                        raise ValueError(f"Aucun enregistrement de fichier trouvé pour '{file_request.file_name}'.")
                    shutil.move(os.path.join(file_service.temp_storage_path, patient_id, file_request.file_name), os.path.join(file_service.storage_path, patient_id, file_request.file_name))
                    file_record.ciphered_dek = file_request.ciphered_dek
                    self.db.commit()
                except Exception as e:
                    raise ValueError(f"Erreur lors de la mise à jour du fichier: {str(e)}")
            case OperationType.DELETE:
                try:
                    file_record = self.db.query(File).filter(File.name == file_request.file_name, File.user_id == patient_id).first()
                    if not file_record:
                        raise ValueError(f"Aucun enregistrement de fichier trouvé pour '{file_request.file_name}'.")
                    os.remove(os.path.join(file_service.storage_path, patient_id, file_request.file_name))
                    self.db.delete(file_record)
                    self.db.commit()
                except Exception as e:
                    raise ValueError(f"Erreur lors de la suppression du fichier: {str(e)}")
            case _:
                raise ValueError(f"Type d'opération inconnu pour la demande '{request_id}'.")
        file_request.status = RequestStatus.APPROVED
        self.db.commit()

    def reject_patient_request(self, patient_id: str, request_id: str):
        """
        Rejette une demande de relation pour un patient donné.
        :param patient_id: ID du patient.
        :param request_id: ID de la demande de relation à rejeter.
        """
        file_request = self.db.query(FileOperationRequest).filter(FileOperationRequest.id == request_id).first()
        if not file_request:
            raise ValueError(f"Aucune demande de relation trouvée avec l'ID '{request_id}'.")

        relation = self.db.query(Relation).filter(Relation.id == file_request.relation_id, Relation.patient_id == patient_id).first()
        if not relation:
            raise ValueError(f"Aucune relation trouvée pour le patient '{patient_id}' avec la demande '{request_id}'.")
        
        file_request.status = RequestStatus.REJECTED
        self.db.commit()

    def doctor_add_patient(self, doctor_id: str, patient_id: str) -> RelationDoctorResponse:
        """
        Crée une relation entre un médecin et un patient.
        :param doctor_id: ID du médecin.
        :param patient_id: ID du patient.
        """
        doctor = self.db.query(User).filter(User.id == doctor_id, User.roles == "doctor").first()
        if not doctor:
            raise ValueError(f"Le médecin avec l'ID '{doctor_id}' n'existe pas ou n'est pas un médecin.")

        patient = self.db.query(User).filter(User.id == patient_id, User.roles == "patient").first()
        if not patient:
            raise ValueError(f"Le patient avec l'ID '{patient_id}' n'existe pas ou n'est pas un patient.")

        doctor_devices = self.db.query(Device).filter(Device.user_id == doctor_id).all()
        if not doctor_devices:
            raise ValueError(f"Le médecin avec l'ID '{doctor_id}' n'a pas de dispositif enregistré.")
        relation = Relation(patient_id=patient_id, doctor_id=doctor_id, is_verified=False)
        self.db.add(relation)
        self.db.commit()
        self.db.refresh(relation)
        return RelationDoctorResponse(relation=relation.id)
    
    def get_unverified_relations(self, user_id: str):
        """
        Récupère les relations non vérifiées d'un utilisateur, dédoublonnées
        par contrepartie et enrichies avec username, direction et public_mek.

        - direction="incoming" : l'utilisateur courant est le patient cible
          d'une demande médecin → il doit l'approuver/refuser. `public_mek`
          contient la JWK publique MEK du médecin pour que le patient puisse
          y wrapper sa KEK une seule fois (au niveau user, plus par device).
        - direction="outgoing" : l'utilisateur courant est le médecin
          demandeur → en attente de vérification par le patient. `public_mek`
          est null (pas pertinent côté médecin demandeur).
        """
        relations = self.db.query(Relation).filter(
            (Relation.patient_id == user_id) | (Relation.doctor_id == user_id),
            Relation.is_verified.is_(False),
        ).all()

        aggregated: dict[str, dict] = {}
        for r in relations:
            is_patient = r.patient_id == user_id
            counterpart_id = r.doctor_id if is_patient else r.patient_id
            if counterpart_id in aggregated:
                continue

            counterpart = self.db.query(User).filter(User.id == counterpart_id).first()
            aggregated[counterpart_id] = {
                "counterpart_id": counterpart_id,
                "username": counterpart.username if counterpart else counterpart_id,
                "role": counterpart.roles if counterpart else None,
                "direction": "incoming" if is_patient else "outgoing",
                # Pour une demande "incoming", la contrepartie est un médecin
                # → on remonte sa public MEK pour permettre au patient de wrap.
                "public_mek": counterpart.public_mek if (counterpart and is_patient) else None,
            }
        return list(aggregated.values())
    
    def get_public_mek_for_doctor(self, doctor_id: str):
        """
        Récupère la clé publique MEK d'un médecin.
        :param doctor_id: ID du médecin.
        :return: Clé publique MEK du médecin.
        """
        doctor = self.db.query(User).filter(User.id == doctor_id, User.roles == "doctor").first()
        if not doctor:
            raise ValueError(f"Le médecin avec l'ID '{doctor_id}' n'existe pas ou n'est pas un médecin.")
        if not doctor.public_mek:
            raise ValueError(f"Le médecin avec l'ID '{doctor_id}' n'a pas de clé publique MEK enregistrée.")
        return {"public_mek": doctor.public_mek}
    
    def store_kek_for_relation(self, user_id: str, relation_id: str, ciphered_kek: str):
        """
        Stocke le KEK chiffré pour une relation spécifique.
        :param user_id: ID de l'utilisateur.
        :param relation_id: ID de la relation.
        :param ciphered_kek: KEK chiffré à stocker.
        """
        relation = self.db.query(Relation).filter(Relation.id == relation_id, (Relation.patient_id == user_id) | (Relation.doctor_id == user_id)).first()
        if not relation:
            raise ValueError(f"La relation avec l'ID '{relation_id}' n'existe pas.")
        relation.ciphered_kek = ciphered_kek
        self.db.commit()
        return relation
    
    def get_relations(self, user_id: str):
        """
        Récupère les relations d'un utilisateur, dédoublonnées par contrepartie
        (patient ou médecin) et enrichies avec le username.

        Une relation existe par device du médecin ; côté UI on ne veut qu'une
        ligne par contrepartie. On agrège donc par counterpart_id et on
        considère la relation "vérifiée" dès qu'au moins un device l'est.
        """
        relations = self.db.query(Relation).filter(
            (Relation.patient_id == user_id) | (Relation.doctor_id == user_id)
        ).all()

        aggregated: dict[str, dict] = {}
        for r in relations:
            counterpart_id = r.doctor_id if r.patient_id == user_id else r.patient_id
            existing = aggregated.get(counterpart_id)
            if existing:
                existing["is_verified"] = existing["is_verified"] or r.is_verified
                continue
            counterpart = self.db.query(User).filter(User.id == counterpart_id).first()
            aggregated[counterpart_id] = {
                "counterpart_id": counterpart_id,
                "username": counterpart.username if counterpart else counterpart_id,
                "role": counterpart.roles if counterpart else None,
                "is_verified": r.is_verified,
            }
        return list(aggregated.values())

    def get_patient_kek_for_doctor(self, doctor_id: str, patient_id: str):
        """
        Retourne le `ciphered_kek` patient pour le médecin courant.

        Le `ciphered_kek` a été produit par le patient au moment de
        `patient_verify_doctor` : il a wrappé sa KEK avec la public MEK du
        médecin (au niveau user, partagée entre tous ses devices). Seul le
        détenteur de la privée MEK correspondante (en mémoire de session côté
        médecin) peut la déballer. Le serveur ne voit jamais la KEK en clair.
        """
        relation = self.db.query(Relation).filter(
            Relation.doctor_id == doctor_id,
            Relation.patient_id == patient_id,
            Relation.is_verified.is_(True),
        ).first()
        if not relation or not relation.ciphered_kek:
            raise ValueError("Aucune relation vérifiée trouvée pour ce patient.")
        return {"ciphered_kek": relation.ciphered_kek}

    def find_patient_by_username(self, username: str):
        """
        Recherche un patient par username exact.

        Restreint aux comptes de rôle "patient" pour éviter de divulguer
        l'existence de médecins via cet endpoint, et pour empêcher un
        médecin d'ajouter un autre médecin comme "patient".
        """
        if not username or not username.strip():
            raise ValueError("Le username est requis.")
        patient = self.db.query(User).filter(
            User.username == username.strip(),
            User.roles == "patient",
        ).first()
        if not patient:
            raise ValueError(f"Aucun patient trouvé avec le username '{username}'.")
        return {"id": patient.id, "username": patient.username}
    
    def delete_relation(self, patient_id: str, doctor_id: str):
        """
        Supprime une relation entre un patient et un médecin.
        :param relation_id: ID de la relation à supprimer.
        """
        user = self.db.query(User).filter(User.id == patient_id, User.roles == "patient").first()
        if not user:
            raise ValueError(f"Le patient avec l'ID '{patient_id}' n'existe pas ou n'est pas un patient.")

        doctor = self.db.query(User).filter(User.id == doctor_id, User.roles == "doctor").first()
        if not doctor:
            raise ValueError(f"Le médecin avec l'ID '{doctor_id}' n'existe pas ou n'est pas un médecin.")

        relations = self.db.query(Relation).filter(Relation.patient_id == patient_id, Relation.doctor_id == doctor_id).all()
        if not relations:
            raise ValueError(f"La relation entre le patient '{patient_id}' et le médecin '{doctor_id}' n'existe pas.")
        
        for relation in relations:
            self.db.delete(relation)
        self.db.commit()
    
        
    def list_doctors(self):
        """
        Récupère la liste de tous les médecins.
        :return: Liste de tous les médecins.
        """
        doctors = self.db.query(User).filter(User.roles == "doctor").all()
        return doctors
    
    def verify_relation(self, patient_id: str, doctor_id: str, ciphered_kek: str):
        """
        Vérifie une relation entre un patient et un médecin en utilisant l'ID du médecin et en stockant le KEK chiffré.
        :param patient_id: ID du patient.
        :param doctor_id: ID du médecin.
        :param ciphered_kek: KEK chiffré à stocker pour la relation vérifiée.
        """
        relation = self.db.query(Relation).filter(Relation.patient_id == patient_id, Relation.doctor_id == doctor_id).first()
        if not relation:
            raise ValueError(f"Aucune relation trouvée pour le patient '{patient_id}' avec le médecin '{doctor_id}'.")
        
        relation.is_verified = True
        relation.ciphered_kek = ciphered_kek
        self.db.commit()
        return relation.id
    
    # temporary
    def create_doctors(self):
        """
        Crée des médecins pour les tests.
        """
        doctor1 = User(id="doctor4", username="Dr. Ben", roles="doctor")
        self.db.add(doctor1)
        doctor1_device = Device(user_id="doctor4", device_name="Ben's Device", public_key={"kty": "RSA", "n": "0vx7agoebGcQSuuPiLJXZptN9nndrQmbXEps2aiAFbWhM78LhWx4cbbfAAtVT86eX", "e": "AQAB"}, is_verified=True)
        self.db.add(doctor1_device)
        doctor1_device2 = Device(user_id="doctor4", device_name="Ben's Second Device", public_key={"kty": "RSA", "n": "0vx7agoebGcQSuuPiLJXZptN9nndrQmbXEps2aiAFbWhM78LhWx4cbbfAAtVT86eX", "e": "AQAB"}, is_verified=True)
        self.db.add(doctor1_device2)
        self.db.commit()

    