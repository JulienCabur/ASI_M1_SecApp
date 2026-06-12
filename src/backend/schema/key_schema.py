"""Schémas Pydantic pour le stockage et la récupération des KEK chiffrés par appareil."""

from pydantic import BaseModel
from schema.device_schema import JWKSchema

class KeyBase(BaseModel):
    """Payload pour associer un KEK chiffré à un appareil enregistré."""

    ciphered_kek: str
    device_id: str

class KeyResponse(BaseModel):
    """Réponse contenant la clé publique de l'appareil et le KEK chiffré correspondant."""

    public_key: JWKSchema
    ciphered_kek: str