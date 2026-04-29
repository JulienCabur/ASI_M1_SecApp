from pydantic import BaseModel

class KeyBase(BaseModel):
    public_key: str
    ciphered_kek: str
