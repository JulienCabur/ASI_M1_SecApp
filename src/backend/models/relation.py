
from sqlalchemy import Boolean, Column, String, ForeignKey, UUID
from sqlalchemy.orm import relationship
from core.database import Base
import uuid

class Relation(Base):
    """
    Modèle de relation entre les utilisateurs.
    """
    __tablename__ = "relations"
    id = Column(UUID, primary_key=True, index=True, default=uuid.uuid4)
    patient_id = Column(String, ForeignKey("users.id"), index=True)
    doctor_id = Column(String, ForeignKey("users.id"), index=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    ciphered_kek = Column(String, nullable=True)
    patient = relationship("User", foreign_keys=[patient_id])
    doctor = relationship("User", foreign_keys=[doctor_id])