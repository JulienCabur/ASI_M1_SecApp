from datetime import datetime, timezone, timedelta
from schema.metadata_schema import MetadataBase

class MetadataService:
    def __init__(self, db):
        self.db = db

    def verify_metadata(self, metadata: MetadataBase) -> tuple[bool, list[str]]:
        """
        Vérifie les métadonnées structurelles d'une requête.
        Retourne (is_anomaly, [raisons]) — toutes les anomalies détectées, pas seulement la première.

        Détections :
        - Décalage horaire client/serveur > 5 min  (replay, horloge manipulée)
        - Timestamp dans le futur > 30 s            (timestamp forgé)
        - Taille négative                           (valeur forgée)
        - Taille > 600 Mo                           (contournement limite frontend)
        - GET/HEAD/OPTIONS avec body                (requête structurellement invalide)
        - Profondeur d'arbre hors norme             (sondage de routes inexistantes)
        """
        reasons= []

        now = datetime.now(timezone.utc)
        client_time = metadata.time
        if client_time.tzinfo is None:
            client_time = client_time.replace(tzinfo=timezone.utc)

        skew_s = (now - client_time).total_seconds()

        if abs(skew_s) > timedelta(minutes=5).total_seconds():
            reasons.append(f"Décalage horaire : {abs(skew_s):.0f}s (max {int(timedelta(minutes=5).total_seconds())}s)")

        if skew_s < -30:
            reasons.append(f"Timestamp dans le futur de {-skew_s:.0f}s")

        if metadata.size_data < 0:
            reasons.append("Taille négative")

        if metadata.size_data > (600 * 1024 * 1024):
            reasons.append(f"Taille excessive : {metadata.size_data} octets")

        if metadata.method.upper() in {"GET", "HEAD", "OPTIONS"} and metadata.size_data > 0:
            reasons.append(f"Corps non attendu sur {metadata.method} ({metadata.size_data} octets)")

        if metadata.tree_depth != 2:
            reasons.append(f"Profondeur d'arbre inhabituelle : {metadata.tree_depth} (attendu 2)")

        return bool(reasons), reasons
