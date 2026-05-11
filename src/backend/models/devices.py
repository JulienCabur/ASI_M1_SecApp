from sqlalchemy import Column, String, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from core.database import Base


class Device(Base):
    __tablename__ = "devices"
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(String, ForeignKey("users.id"))
    device_name = Column(String)
    public_key = Column(JSONB, nullable=False)
    ciphered_kek = Column(String, nullable=True) # KEK pour patient | MEK_PRK pour doctor
    is_verified = Column(Boolean, default=False)
    user = relationship("User", back_populates="devices")

