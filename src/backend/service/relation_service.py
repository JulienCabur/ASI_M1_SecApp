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

        relation = Relation(patient_id=patient_id, doctor_id=doctor_id, is_verified=True)
        self.db.add(relation)
        self.db.commit()
        self.db.refresh(relation)
        final_relation = RelationBase(
            relation_id=relation.id,
            public_key=doctor.public_mek,
        )
        if not doctor.public_mek:
            raise ValueError(f"Le médecin avec l'ID '{doctor_id}' n'a pas de dispositif vérifié.")

        return RelationResponse(relation=final_relation)


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
        par contrepartie et enrichies avec username, direction et devices.

        - direction="incoming" : l'utilisateur courant est le patient cible
          d'une demande médecin → il doit l'approuver/refuser. La liste
          `devices` contient les clés publiques des devices du médecin pour
          que le patient puisse wrap sa KEK avec.
        - direction="outgoing" : l'utilisateur courant est le médecin
          demandeur → en attente de vérification par le patient.
        """
        relations = self.db.query(Relation).filter(
            (Relation.patient_id == user_id) | (Relation.doctor_id == user_id),
            Relation.is_verified.is_(False),
        ).all()

        aggregated: dict[str, dict] = {}
        for r in relations:
            is_patient = r.patient_id == user_id
            counterpart_id = r.doctor_id if is_patient else r.patient_id

            device_info = None
            if r.doctor_device_id:
                device = self.db.query(Device).filter(Device.id == r.doctor_device_id).first()
                if device:
                    device_info = {
                        "device_id": str(device.id),
                        "public_key": device.public_key,
                    }

            if counterpart_id in aggregated:
                if device_info:
                    aggregated[counterpart_id]["devices"].append(device_info)
                continue

            counterpart = self.db.query(User).filter(User.id == counterpart_id).first()
            aggregated[counterpart_id] = {
                "counterpart_id": counterpart_id,
                "username": counterpart.username if counterpart else counterpart_id,
                "role": counterpart.roles if counterpart else None,
                "direction": "incoming" if is_patient else "outgoing",
                "devices": [device_info] if device_info else [],
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

    def get_patient_kek_for_doctor(self, doctor_id: str, doctor_device_id: str, patient_id: str):
        """
        Retourne le `ciphered_kek` patient pour le device courant du médecin.

        Le `ciphered_kek` a été produit par le patient au moment du
        `patient_verify_doctor` : il a wrappé sa KEK avec la clé publique RSA
        de ce device → seul le détenteur de la privée RSA correspondante (ce
        device, en local) peut le déballer. Le serveur ne voit jamais la KEK
        en clair.
        """
        device = self.db.query(Device).filter(
            Device.id == doctor_device_id,
            Device.user_id == doctor_id,
        ).first()
        if not device:
            raise ValueError("Device introuvable ou ne vous appartient pas.")

        relation = self.db.query(Relation).filter(
            Relation.doctor_id == doctor_id,
            Relation.patient_id == patient_id,
            Relation.is_verified.is_(True),
        ).first()
        if not relation or not relation.ciphered_kek:
            raise ValueError("Aucune relation vérifiée trouvée pour ce patient sur ce device.")
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

    