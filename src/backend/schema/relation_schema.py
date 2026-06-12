"""Schémas Pydantic pour les relations patient-médecin et le partage de clés."""

from pydantic import BaseModel
from typing import List
from uuid import UUID
from schema.device_schema import JWKSchema

class RelationBase(BaseModel):
    """Relation entre un patient et un médecin, avec la clé publique associée."""

    relation_id: UUID
    public_key: JWKSchema

class RelationResponse(BaseModel):
    """Liste de relations d'un utilisateur."""

    relation: List[RelationBase]

class RelationDoctorResponse(BaseModel):
    """Identifiant de relation retourné lors de la vérification par le patient."""

    relation: UUID