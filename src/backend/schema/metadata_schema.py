"""Schémas Pydantic pour les métadonnées structurelles des requêtes HTTP,
utilisées par le middleware de détection d'anomalies."""

from pydantic import BaseModel
from datetime import datetime

class MetadataBase(BaseModel):
    """Métadonnées extraites d'une requête entrante (timestamp, taille, profondeur de chemin)."""

    time: datetime
    size_data: int
    privilege_need: str | None = None
    tree_depth: int
    method: str

class MetadataResponse(MetadataBase):
    """Résultat de l'analyse des métadonnées avec indicateur d'anomalie."""

    id: str
    is_anomaly: bool
    anomaly_reason: str | None = None
