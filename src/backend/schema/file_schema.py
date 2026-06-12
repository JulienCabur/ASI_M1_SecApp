"""Schéma Pydantic pour les métadonnées d'un fichier médical chiffré."""

from pydantic import BaseModel

class FileBase(BaseModel):
    """Métadonnées d'un fichier médical : chemin de stockage, nom et DEK chiffré."""

    path: str
    name: str
    ciphered_dek: str
