import datetime
import os
import requests
import hashlib
import urllib3
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.backends import default_backend
import json
import base64

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class LogsService:
    """
    Classe de service pour la gestion des logs.
    """
    def __init__(self):
        """
        Initialise le service de logs.
        """
        self.category = ["INFO", "WARNING", "ERROR", "DEBUG", "CRITICAL"]
        self.sequence = 0
        self.logstash_url = os.getenv("LOGSTASH_URL", "https://logstash:5044")
        self.service_name = "backend_python"
        self.previous_hash = "0000000000000000000000000000000000000000000000000000000000000000"
        self.source_ip = "0.0.0.0"
        self.public_cert_path = "/app/logstash/server.crt"

    def _load_public_cert(self):
        """
        Charge le certificat public pour les communications sécurisées.
        """
        try:
            with open(self.public_cert_path, "rb") as cert_file:
                cert_data = cert_file.read()
            
            cert = load_pem_x509_certificate(cert_data, default_backend())
            return cert.public_key()
        except Exception as e:
            print(f"Erreur lors du chargement du certificat public: {e}")
            return None
        
    def _encrypt_log_data(self, log_data: dict) -> dict:
        """
        Chiffre les données du log à l'aide du certificat public.
        """
        if not self.public_cert_path:
            print("Aucun certificat public disponible pour le chiffrement.")
            raise ValueError("Aucun certificat public disponible pour le chiffrement.")
        
        try:
            json_str = json.dumps(log_data)
            encrypted = self.public_key.encrypt(
                json_str.encode('utf-8'),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return base64.b64encode(encrypted).decode('utf-8')
        except Exception as e:
            print(f"Erreur lors du chiffrement des données du log: {e}")
            raise json.dumps(log_data)

    def add_logs(self, action: str, log_level: str, user_id: str, user_role: str, patient_id: str = "null"):
        """
        Ajoute un log à Logstash.
        """
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

        raw_string = f"{timestamp}{log_level}{self.service_name}{action}{user_id}{user_role}{user_role}{self.source_ip}{patient_id}{self.sequence}{self.previous_hash}"

        valid_hash = hashlib.sha256(raw_string.encode('utf-8')).hexdigest()

        log_data = {
            "@timestamp": timestamp,
            "log": {
                "level": log_level
            },
            "service": {
                "name": self.service_name
            },
            "message": f"Action {action} effectuée par l'utilisateur.",
            "event": {
                "action": action
            },
            "user": {
                "id": user_id,
                "roles": [user_role]
            },
            "source": {
                "ip": self.source_ip
            },
            "patient": {
                "id": patient_id
            },
            "audit_chain": {
                "sequence": self.sequence,
                "hash": valid_hash,
                "previous_hash": self.previous_hash
            }
        }
        
        self.previous_hash = valid_hash
        self.sequence += 1

        encrypted_log_data = self._encrypt_log_data(log_data)

        try:
            response = requests.post(self.logstash_url, data=encrypted_log_data, headers={'Content-Type': 'application/json'}, verify=False, timeout=10)
            print(f"Log ECS envoyé - Action: {action}")
        except Exception as e:
            print(f"Erreur lors de l'envoi du log à Logstash: {e}")
        
        #return valid_hash
