"""Énumérations pour les demandes d'opérations sur fichiers médicaux."""

import enum

class OperationType(str, enum.Enum):
    """Type d'opération demandée sur un fichier (création, mise à jour, suppression)."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

class RequestStatus(str, enum.Enum):
    """Statut d'une demande d'opération en attente de validation patient."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"