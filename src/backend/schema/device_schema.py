"""Schémas Pydantic pour la gestion des appareils et des clés cryptographiques."""

from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from typing import List, Optional

class JWKSchema(BaseModel):
    """Représentation d'une clé publique au format JWK (JSON Web Key)."""
    kty: str = Field(..., description="Key Type (ex: RSA)")
    e: str = Field(..., description="Public Exponent (ex: AQAB)")
    n: str = Field(..., description="Modulus (la clé mathématique)")
    alg: Optional[str] = Field(None, description="Algorithm (ex: RSA-OAEP-256)")
    ext: Optional[bool] = Field(None, description="Extractable")
    key_ops: Optional[List[str]] = Field(None, description="Key Operations (ex: ['encrypt'])")

    class Config:
        extra = "allow"

class DeviceRegister(BaseModel):
    """Payload d'enregistrement d'un nouvel appareil."""

    name: str
    public_key: JWKSchema

class DeviceResponse(BaseModel):
    """Réponse renvoyée après enregistrement ou listage d'un appareil."""
    id: UUID
    device_name: str
    is_verified: bool
    public_key: JWKSchema
    model_config = ConfigDict(from_attributes=True)
