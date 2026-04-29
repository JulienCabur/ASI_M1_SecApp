from pydantic import BaseModel

class FileBase(BaseModel):
    path: str
    name: str
    ciphered_dek: str
