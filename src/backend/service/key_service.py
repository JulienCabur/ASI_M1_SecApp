
from sqlalchemy.orm import Session
from schema.key_schema import KeyBase
from models.user import User
from dotenv import load_dotenv

load_dotenv()  # Charger les variables d'environnement depuis le fichier .env


class KeyService:
    """
    Classe pour gérer les opérations liées aux clés.
    """
    def __init__(self, db: Session):
        """
        Initialise le service de gestion de l'authentification avec une session de base de données.
        :param db: Session de base de données SQLAlchemy.
        """
        self.db = db

    def store_user_keys(self, user_id: str, public_key: str, ciphered_kek: str) -> None:
        """
        Stocke les clés de l'utilisateur dans la base de données.
        :param user_id: ID de l'utilisateur.
        :param public_key: Clé publique de l'utilisateur.
        :param ciphered_kek: KEK chiffré de l'utilisateur.
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise Exception("Utilisateur non trouvé")
        user.public_key = public_key
        user.ciphered_kek = ciphered_kek
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_user_keys(self, user_id: str) -> KeyBase:
        """
        Récupère les clés de l'utilisateur depuis la base de données.
        :param user_id: ID de l'utilisateur.
        :return: Dictionnaire contenant la clé publique et le KEK chiffré de l'utilisateur.
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise Exception("Utilisateur non trouvé")
        return KeyBase(public_key=user.public_key, ciphered_kek=user.ciphered_kek)