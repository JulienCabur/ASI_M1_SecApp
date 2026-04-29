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
    public_key = Column(String, nullable=True)
    ciphered_kek = Column(String, nullable=True)
    challenge_nonce = Column(String, nullable=True)
    challenge_timestamp = Column(String, nullable=True)

class Relation(Base):
    """
    Modèle de relation entre les utilisateurs.
    """
    __tablename__ = "relations"
    id = Column(UUID, primary_key=True, index=True)
    patient_id = Column(String, ForeignKey("users.id"), index=True)
    doctor_id = Column(String, ForeignKey("users.id"), index=True)
    ciphered_kek = Column(String, nullable=True)
    patient = relationship("User", foreign_keys=[patient_id])
    doctor = relationship("User", foreign_keys=[doctor_id])

class File(Base):
    """
    Modèle de fichier pour la base de données.
    """
    __tablename__ = "files"
    uuid = Column(UUID, primary_key=True, index=True)
    name = Column(String, nullable=False)
    date = Column(String, nullable=False)
    user_id = Column(String, ForeignKey("users.id"),nullable=False)
    ciphered_dek = Column(String, nullable=False)
    user = relationship("User", foreign_keys=[user_id])

