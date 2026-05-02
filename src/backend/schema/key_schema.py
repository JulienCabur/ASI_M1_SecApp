from pydantic import BaseModel, ConfigDict
from typing import Optional
from schema.device_schema import JWKSchema

class KeyBase(BaseModel):
    ciphered_kek: str
    device_id: str

class KeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_key: JWKSchema
    ciphered_kek: Optional[str] = None
    is_verified: bool