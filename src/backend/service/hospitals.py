from sqlalchemy.orm import Session
from typing import List, Dict
from models.hostpials import Hospital

class HospitalService:
    """
    Classe pour gérer les opérations liées aux hôpitaux.
    """
    def __init__(self, db: Session):
        """
        Initialise le service de gestion des hôpitaux avec une session de base de données.
        :param db: Session de base de données SQLAlchemy.
        """
        self.db = db
        hospital_count = self.db.query(Hospital).count()
        if hospital_count == 0:
            default_hospitals = [
                Hospital(id="1", name="Hôpital Saint-Louis"),
                Hospital(id="2", name="Hôpital Necker-Enfants Malades"),
                Hospital(id="3", name="Hôpital Cochin"),
                Hospital(id="4", name="Hôpital Pitié-Salpêtrière"),
                Hospital(id="5", name="Hôpital Bichat-Claude Bernard")
            ]
            self.db.add_all(default_hospitals)
            self.db.commit()

    def get_hospitals(self) -> List[str]:
        """Retourne la liste des hôpitaux disponibles (id + nom)."""
        hospitals = self.db.query(Hospital).all()
        hospital_names = [hospital.name for hospital in hospitals]
        return hospital_names