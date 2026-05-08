from pydantic import BaseModel
from typing import List
from uuid import UUID
from schema.device_schema import JWKSchema

class RelationBase(BaseModel):
    relation_id: UUID
    public_key: JWKSchema

class RelationResponse(BaseModel):
    relation: RelationBase

class RelationDoctorResponse(BaseModel):
    relation: UUID