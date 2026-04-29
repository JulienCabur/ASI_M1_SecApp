from pydantic import BaseModel, EmailStr, Field

class AuthBase(BaseModel):
    username: str
    email: str


class PasswordResetRequest(BaseModel):
    email: EmailStr = Field(..., description="Adresse e-mail du compte à réinitialiser")

class UserInDB(AuthBase):
    id: str
    roles: list[str]

class CertificateRequest(AuthBase):
    first_name: str
    last_name: str

class ChallengeResponse(BaseModel):
    nonce: str
    timestamp: str

class ChallengeResponseRequest(BaseModel):
    username: str = Field(..., example="dr.house")
    nonce: str = Field(..., description="Le nonce hexadécimal reçu lors du challenge")
    timestamp: str = Field(..., description="Le timestamp ISO reçu lors du challenge")
    signature: str = Field(..., description="Signature hexadécimale (PSS/SHA256)")
    certificate: str = Field(..., description="Le certificat PEM du docteur")


class CertLoginProofRequest(ChallengeResponseRequest):
    """Preuve de possession du certificat avant redirection OIDC.
    `redirect_to` est conservé dans le cookie `oidc_state` pour ramener
    l'utilisateur sur la page initialement demandée après le callback Keycloak."""
    redirect_to: str = Field(default="/", description="Chemin frontend de retour après login")


class CertLoginProofResponse(BaseModel):
    authorize_url: str = Field(..., description="URL Keycloak vers laquelle le navigateur doit naviguer")
