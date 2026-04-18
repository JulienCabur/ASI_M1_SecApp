from pydantic import BaseModel
from typing import Dict, Any

class AuthBase(BaseModel):
    id: str

class UserInDB(AuthBase):
    username: str
    email: str
    roles: list[str]

class CertificateRequest(AuthBase):
    common_name: str
    email: str