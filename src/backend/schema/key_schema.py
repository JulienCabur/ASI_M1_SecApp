from pydantic import BaseModel

class KeyBase(BaseModel):
    ciphered_kek: str
    device_id: str

class KeyResponse(BaseModel):
    public_key: str
    ciphered_kek: str