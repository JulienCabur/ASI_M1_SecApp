
from sqlalchemy.orm import Session
from models.devices import Device
from schema.key_schema import KeyResponse
from models.user import User
from dotenv import load_dotenv

load_dotenv()  # Charger les variables d'environnement depuis le fichier .env


class DeviceService:
    """
    Classe pour gérer les opérations liées aux dispositifs.
    """
    def __init__(self, db: Session):
        """
        Initialise le service de gestion de l'authentification avec une session de base de données.
        :param db: Session de base de données SQLAlchemy.
        """
        self.db = db
    
    def register_device(self, user_id: str, device_name: str, public_key: str) -> Device:
        """
        Enregistre un nouveau dispositif pour un utilisateur donné.
        :param user_id: ID de l'utilisateur.
        :param device_name: Nom du dispositif à enregistrer.
        :param public_key: Clé publique du dispositif.
        :return: Le dispositif enregistré.
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise Exception("Utilisateur non trouvé")
        if self.db.query(Device).filter(Device.user_id == user_id).first():
            new_device = Device(device_name=device_name, user_id=user_id, is_verified=False, public_key=public_key)
        else:
            new_device = Device(device_name=device_name, user_id=user_id, is_verified=True, public_key=public_key)
        self.db.add(new_device)
        self.db.commit()
        self.db.refresh(new_device)
        return new_device

    def list_all_devices(self, user_id: str) -> list:
        """
        Liste tous les dispositifs d'un utilisateur donné.
        :param user_id: ID de l'utilisateur.
        :return: Liste de tous les dispositifs.
        """
        return self.db.query(Device).filter(Device.user_id == user_id).all()

    def revoke_device(self, user_id: str, device_id: str) -> None:
        """
        Révoque et supprime un dispositif (vérifié ou non) appartenant à l'utilisateur.
        :param user_id: ID de l'utilisateur.
        :param device_id: ID du dispositif à révoquer.
        """
        device = self.db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise Exception("Dispositif non trouvé")
        if device.user_id != user_id:
            raise Exception("Le dispositif n'appartient pas à l'utilisateur")
        self.db.delete(device)
        self.db.commit()

    def reject_device(self, user_id: str, device_id: str) -> None:
        """
        Rejette et supprime un dispositif en attente d'approbation.
        :param user_id: ID de l'utilisateur.
        :param device_id: ID du dispositif à rejeter.
        """
        device = self.db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise Exception("Dispositif non trouvé")
        if device.user_id != user_id:
            raise Exception("Le dispositif n'appartient pas à l'utilisateur")
        if device.is_verified:
            raise Exception("Impossible de rejeter un dispositif déjà vérifié")
        self.db.delete(device)
        self.db.commit()

    def list_unverified_devices(self, user_id: str) -> list:
        """
        Liste les dispositifs non vérifiés pour un utilisateur donné.
        :param user_id: ID de l'utilisateur.
        :return: Liste des dispositifs non vérifiés.
        """
        devices = self.db.query(Device).filter(Device.user_id == user_id, Device.is_verified.is_(False)).all()
        return devices

    def verify_device(self, user_id: str, device_id: str, ciphered_kek: str) -> Device:
        """
        Vérifie un dispositif pour un utilisateur donné.
        :param user_id: ID de l'utilisateur.
        :param device_id: ID du dispositif à vérifier.
        :param ciphered_kek: KEK chiffré du dispositif à vérifier.
        :return: Le dispositif vérifié.
        """
        device = self.db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise Exception("Dispositif non trouvé")
        if device.user_id != user_id:
            raise Exception("Le dispositif n'appartient pas à l'utilisateur")
        device.is_verified = True
        device.ciphered_kek = ciphered_kek
        self.db.commit()
        self.db.refresh(device)
        return device

    def store_device_keys(self, user_id: str, ciphered_kek: str, device_id: str) -> None:
        """
        Stocke les clés du dispositif dans la base de données.
        :param user_id: ID de l'utilisateur.
        :param ciphered_kek: KEK chiffré du dispositif.
        :param device_id: ID du dispositif.
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise Exception("Utilisateur non trouvé")
        device = self.db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise Exception("Dispositif non trouvé")
        if device.user_id != user_id:
            raise Exception("Le dispositif n'appartient pas à l'utilisateur")
        device.ciphered_kek = ciphered_kek
        self.db.commit()
        self.db.refresh(device)
        return device

    def get_device_keys(self, user_id: str, device_id: str) -> KeyResponse:
        """
        Récupère les clés du dispositif depuis la base de données.
        :param user_id: ID de l'utilisateur.
        :param device_id: ID du dispositif.
        :return: Dictionnaire contenant la clé publique et le KEK chiffré du dispositif.
        """
        device = self.db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise Exception("Dispositif non trouvé")
        if device.user_id != user_id:
            raise Exception("Le dispositif n'appartient pas à l'utilisateur")
        return KeyResponse(
            public_key=device.public_key,
            ciphered_kek=device.ciphered_kek,
            is_verified=device.is_verified,
        )