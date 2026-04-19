"""
Ce module définit le modèle d'utilisateur pour la base de données.
Il utilise SQLAlchemy pour mapper les attributs de l'utilisateur aux colonnes de la table.
"""

from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from core.database import Base

class User(Base):
    """
    Modèle d'utilisateur pour la base de données.
    """
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    roles = Column(String, nullable=False)
    public_key = Column(String, nullable=True)
    challenge_nonce = Column(String, nullable=True)
    challenge_timestamp = Column(String, nullable=True)
