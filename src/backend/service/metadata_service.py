from models.user import User
from schema.metadata_schema import MetadataBase

class MetadataService:
    """
    Classe pour gérer les opérations liées aux métadonnées.
    """
    def __init__(self, db):
        """
        Initialise le service de gestion des métadonnées avec une session de base de données.
        :param db: Session de base de données SQLAlchemy.
        """
        self.db = db
    
    def verify_metadata(self, user_id: str, metadata: MetadataBase) -> None:
        """
        Vérifie les métadonnées d'un utilisateur.
        :param user_id: ID de l'utilisateur.
        :param metadata: Métadonnées à vérifier.
        :return: Métadonnées de l'utilisateur.
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"L'utilisateur avec l'ID '{user_id}' n'existe pas.")

        

        return None