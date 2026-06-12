"""Modèle SQLAlchemy représentant une demande d'opération sur fichier
(upload/delete) initiée par un médecin et en attente d'approbation patient."""

from sqlalchemy import Column, DateTime, Enum, String, ForeignKey, UUID, func
from sqlalchemy.orm import relationship
from schema.file_requests_schema import OperationType, RequestStatus
from core.database import Base
import uuid

class FileOperationRequest(Base):
    """Demande d'opération sur fichier soumise par un médecin dans le cadre
    d'une relation patient-médecin. Le patient doit approuver ou rejeter
    la demande avant que l'opération ne soit effectuée.
    """

    __tablename__ = "file_operation_requests"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    relation_id = Column(UUID(as_uuid=True), ForeignKey("relations.id", ondelete="CASCADE"), nullable=False)
    operation_type = Column(Enum(OperationType), nullable=False)
    status = Column(Enum(RequestStatus), default=RequestStatus.PENDING, index=True)
    file_name = Column(String, nullable=False)
    date = Column(String, nullable=False)
    ciphered_dek = Column(String, nullable=True)
    relation = relationship("Relation", back_populates="file_requests")