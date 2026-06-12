from datetime import datetime, timezone, timedelta
from schema.metadata_schema import MetadataBase


class MetadataService:
    def __init__(self, db):
        self.db = db

    def verify_metadata(
        self, metadata: MetadataBase
    ) -> tuple[bool, list[str], list[str]]:
        """Retourne (is_anomaly, blocking_reasons, warning_reasons).

        Les raisons bloquantes entraînent un rejet HTTP 400 immédiat.
        Les raisons d'avertissement sont uniquement loguées.
        """
        blocking: list[str] = []
        warnings: list[str] = []

        now = datetime.now(timezone.utc)
        client_time = metadata.time
        if client_time.tzinfo is None:
            client_time = client_time.replace(tzinfo=timezone.utc)

        skew_s = (now - client_time).total_seconds()
        if skew_s < -30:
            blocking.append(f"Timestamp dans le futur de {-skew_s:.0f}s (max 30s)")

        elif abs(skew_s) > timedelta(minutes=5).total_seconds():
            warnings.append(f"Décalage horaire : {abs(skew_s):.0f}s (max 300s)")

        if metadata.size_data < 0:
            blocking.append("Content-Length négatif")

        if metadata.size_data > (600 * 1024 * 1024):
            blocking.append(f"Taille excessive : {metadata.size_data} octets")

        if metadata.method.upper() in {"GET", "HEAD", "OPTIONS"} and metadata.size_data > 0:
            warnings.append(f"Corps non attendu sur {metadata.method} ({metadata.size_data} octets)")

        if metadata.tree_depth != 2:
            warnings.append(f"Profondeur d'arbre inhabituelle : {metadata.tree_depth} (attendu 2)")

        is_anomaly = bool(blocking or warnings)
        return is_anomaly, blocking, warnings
