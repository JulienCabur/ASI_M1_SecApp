from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

class JWKSchema(BaseModel):
    kty: str = Field(..., description="Key Type (ex: RSA)")
    e: str = Field(..., description="Public Exponent (ex: AQAB)")
    n: str = Field(..., description="Modulus (la clé mathématique)")
    alg: Optional[str] = Field(None, description="Algorithm (ex: RSA-OAEP-256)")
    ext: Optional[bool] = Field(None, description="Extractable")
    key_ops: Optional[List[str]] = Field(None, description="Key Operations (ex: ['encrypt'])")

    class Config:
        extra = "allow"

class DeviceRegister(BaseModel):
    name: str
    public_key: JWKSchema
