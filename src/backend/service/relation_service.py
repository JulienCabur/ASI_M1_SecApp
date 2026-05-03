from models.relation import Relation
from models.user import User
from models.devices import Device
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

        doctor_devices = self.db.query(Device).filter(Device.user_id == doctor_id).all()
        if not doctor_devices:
            raise ValueError(f"Le médecin avec l'ID '{doctor_id}' n'a pas de dispositif enregistré.")
        relations = []
        public_keys = []
        for device in doctor_devices:
            relation = Relation(patient_id=patient_id, doctor_id=doctor_id, doctor_device_id=device.id, is_verified=True)
            public_keys.append(device.public_key)
            self.db.add(relation)
            self.db.commit()
            self.db.refresh(relation)
            relations.append(RelationBase(
                relation_id=relation.id,
                public_key=device.public_key
            ))
        if not public_keys:
            raise ValueError(f"Le médecin avec l'ID '{doctor_id}' n'a pas de dispositif vérifié.")

        return RelationResponse(relation=relations)
    
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
        relations = []
        for device in doctor_devices:
            relation = Relation(patient_id=patient_id, doctor_id=doctor_id, doctor_device_id=device.id, is_verified=False)
            self.db.add(relation)
            self.db.commit()
            self.db.refresh(relation)
            relations.append(relation.id)

        return RelationDoctorResponse(relation=relations)
    
    def get_unverified_relations(self, user_id: str):
        """
        Récupère les relations non vérifiées d'un utilisateur.
        :param user_id: ID de l'utilisateur.
        :return: Liste des relations non vérifiées de l'utilisateur.
        """
        relations = self.db.query(Relation).filter((Relation.patient_id == user_id) | (Relation.doctor_id == user_id), Relation.is_verified.is_(False)).all()
        return relations
    
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
        Récupère les relations d'un utilisateur.
        :param user_id: ID de l'utilisateur.
        :return: Liste des relations de l'utilisateur.
        """
        relations = self.db.query(Relation).filter((Relation.patient_id == user_id) | (Relation.doctor_id == user_id)).all()
        return relations
    
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

    