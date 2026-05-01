from pydantic import BaseModel
from schema.device_schema import JWKSchema

class KeyBase(BaseModel):
    ciphered_kek: str
    device_id: str

class KeyResponse(BaseModel):
    public_key: JWKSchema
    ciphered_kek: str