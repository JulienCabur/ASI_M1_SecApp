from sqlalchemy.orm import Session

class FileService:
    """
    Classe pour gérer les opérations liées à l'authentification.
    """
    def __init__(self, db: Session):
        """
        Initialise le service de gestion de l'authentification avec une session de base de données.
        :param db: Session de base de données SQLAlchemy.
        """
        self.db = db
    
    def generate_csr(self, common_name: str):
        pass