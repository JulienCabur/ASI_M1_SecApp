

from sqlalchemy import Column, String, ForeignKey, UUID
from sqlalchemy.orm import relationship
from core.database import Base
import uuid

class File(Base):
    """
    Modèle de fichier pour la base de données.
    """
    __tablename__ = "files"
    uuid = Column(UUID, primary_key=True, index=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    date = Column(String, nullable=False)
    user_id = Column(String, ForeignKey("users.id"),nullable=False)
    ciphered_dek = Column(String, nullable=False)
    user = relationship("User", foreign_keys=[user_id])