from pydantic import BaseModel

class AuthBase(BaseModel):
    username: str
    email: str

class UserInDB(AuthBase):
    id: str
    roles: list[str]

class CertificateRequest(AuthBase):
    first_name: str
    last_name: str

class ChallengeResponse(BaseModel):
    nonce: str
    timestamp: str
