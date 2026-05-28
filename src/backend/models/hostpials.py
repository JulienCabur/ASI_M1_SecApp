from sqlalchemy import Column, String
from core.database import Base

class Hospital(Base):
    """
    Modèle d'hôpital pour la base de données.
    """
    __tablename__ = "hospitals"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
