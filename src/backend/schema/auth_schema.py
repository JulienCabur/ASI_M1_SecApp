from pydantic import BaseModel, Field

class AuthBase(BaseModel):
    username: str
    email: str

class UserInDB(AuthBase):
    id: str
    roles: list[str]

class CertificateRequest(AuthBase):
    first_name: str
    last_name: str
    organization: str
    date_of_birth: str

class ChallengeResponse(BaseModel):
    nonce: str
    timestamp: str

class ChallengeResponseRequest(BaseModel):
    username: str = Field(..., example="dr.house")
    nonce: str = Field(..., description="Le nonce hexadécimal reçu lors du challenge")
    timestamp: str = Field(..., description="Le timestamp ISO reçu lors du challenge")
    signature: str = Field(..., description="Signature hexadécimale (PSS/SHA256)")
    certificate: str = Field(..., description="Le certificat PEM du docteur")
