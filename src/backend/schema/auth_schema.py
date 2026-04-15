from pydantic import BaseModel
from typing import Dict, Any

class AuthBase(BaseModel):
    pass

class UserInDB(AuthBase):
    id: str
    username: str
    email: str
    roles: list[str]
