import os
import hashlib
import re
import base64

class AuthenticityService:
    """
    Classe pour gérer les opérations liées aux fichiers.
    """
    def __init__(self):
        """
        Initialise le service de gestion des fichiers avec une session de base de données et un chemin de stockage.
        :param db: Session de base de données SQLAlchemy.
        :param storage_path: Chemin du répertoire de stockage des fichiers.
        """
        self.path = "/app/certs/"
    
    def download_ca(self) -> str:
        """
        Télécharge le fichier de l'autorité de certification.
        :return: Chemin du fichier de l'autorité de certification.
        """
        ca_file = "ca-chain.pem"  # Nom du fichier de l'autorité de certification
        ca_path = os.path.join(self.path, ca_file)

        if not os.path.exists(ca_path):
            raise FileNotFoundError(f"Le fichier '{ca_file}' n'existe pas dans le répertoire de stockage.")

        return ca_path

    def get_hash(self) -> str:
        """
        Récupère le hash (thumbprint) du fichier.
        :return: Hash du fichier.
        """
        ca_path = self.download_ca()

        with open(ca_path, "r", encoding="utf-8") as f:
            content = f.read()

        match = re.search(r"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----", content, re.DOTALL)

        if not match:
            raise ValueError("Le contenu du fichier ne contient pas de certificat valide.")
        
        b64_string = match.group(1).replace("\n", "").replace("\r", "")

        der_data = base64.b64decode(b64_string)

        hash_sha1 = hashlib.sha1(der_data).hexdigest().upper()

        return hash_sha1