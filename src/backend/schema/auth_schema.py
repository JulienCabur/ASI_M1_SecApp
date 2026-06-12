"""Schémas Pydantic pour l'authentification, la gestion des utilisateurs
et les flux de connexion par certificat X.509."""

from pydantic import BaseModel, EmailStr, Field

class AuthBase(BaseModel):
    """Champs communs à tous les modèles d'authentification."""

    username: str
    email: EmailStr


class PasswordResetRequest(BaseModel):
    """Requête de réinitialisation de mot de passe par e-mail."""

    email: EmailStr = Field(..., description="Adresse e-mail du compte à réinitialiser")

class UserInDB(AuthBase):
    """Représentation de l'utilisateur authentifié extrait du JWT Keycloak."""

    id: str
    roles: list[str]

class CertificateRequest(AuthBase):
    """Requête de génération et signature d'un certificat X.509 médecin.

    Le CSR est généré côté navigateur (clé privée jamais transmise au serveur).
    """
    first_name: str
    last_name: str
    organization: str
    date_of_birth: str
    # CSR PEM généré côté navigateur. La clé privée correspondante reste dans
    # le navigateur ; le back se contente de la faire signer par la PKI puis
    # renvoie le certificat signé pour que le navigateur assemble le .p12.
    csr: str

class ChallengeResponse(BaseModel):
    """Challenge cryptographique envoyé au client pour preuve de possession de la clé privée."""

    nonce: str
    timestamp: str

class ChallengeResponseRequest(BaseModel):
    """Réponse au challenge signée par le client avec sa clé privée de certificat."""
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
    flow_type: str = Field(default="standard", description="Type de flux OIDC (standard | add_device)")


class CertLoginProofResponse(BaseModel):
    authorize_url: str = Field(..., description="URL Keycloak vers laquelle le navigateur doit naviguer")
