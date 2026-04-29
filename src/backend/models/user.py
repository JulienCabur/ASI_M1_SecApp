"""
Ce module définit le modèle d'utilisateur pour la base de données.
Il utilise SQLAlchemy pour mapper les attributs de l'utilisateur aux colonnes de la table.
"""

from sqlalchemy import Column, String, ForeignKey, UUID
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
    challenge_nonce = Column(String, nullable=True)
    challenge_timestamp = Column(String, nullable=True)
    devices = relationship("Device", back_populates="user")
    files = relationship("File", back_populates="user")

