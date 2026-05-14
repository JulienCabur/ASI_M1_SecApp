import datetime
import time
import os
import json
import requests
import hashlib
import base64
import urllib3
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.backends import default_backend

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class LogsService:
    """
    Classe de service pour la gestion des logs.
    """
    def __init__(self, service_name: str = "backend_python"):
        """
        Initialise le service de logs.
        """
        self.category = ["INFO", "WARNING", "ERROR", "DEBUG", "CRITICAL"]
        self.sequence = 0
        self.logstash_url = os.getenv("LOGSTASH_URL", "https://logstash:5044")
        self.service_name = service_name
        self.previous_hash = "0000000000000000000000000000000000000000000000000000000000000000"
        self.source_ip = "0.0.0.0"
        self.public_cert_path = "/app/certs/logstash.crt"

        self.session_key = None
        self.encrypted_session_key_b64 = None
        self.session_id = None
        self.session_creation_time = 0
        self.session_rotation_interval = 300

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
        
    def _get_rotate_session(self) -> tuple:
        current_time = time.time()

        if self.session_key is None or (current_time - self.session_creation_time) > self.session_rotation_interval:
            self.session_key = os.urandom(32)
            self.session_id = os.urandom(8).hex()

            public_key = self._load_public_cert()
            if public_key is None:
                raise ValueError("Impossible de charger le certificat public pour le chiffrement de la session.")
            
            encrypted_key = public_key.encrypt(
                self.session_key,
                asym_padding.PKCS1v15()
            )
            self.encrypted_session_key_b64 = base64.b64encode(encrypted_key).decode('utf-8')
            self.session_creation_time = current_time

        return self.session_key, self.encrypted_session_key_b64, self.session_id

    def _encrypt_log_data(self, log_data: dict) -> dict:
        """
        Chiffre les données du log à l'aide du certificat public.
        """
        aes_key, enc_key_b64, session_id = self._get_rotate_session()

        iv = os.urandom(12)
        log_bytes = json.dumps(log_data).encode('utf-8')

        cipher = Cipher(algorithms.AES(aes_key), modes.GCM(iv))
        encryptor = cipher.encryptor()
        encrypted_payload = encryptor.update(log_bytes) + encryptor.finalize()

        return {
            "session_id": session_id,
            "encrypted_key": enc_key_b64,
            "iv": base64.b64encode(iv).decode('utf-8'),
            "tag": base64.b64encode(encryptor.tag).decode('utf-8'),
            "payload": base64.b64encode(encrypted_payload).decode('utf-8')
        }

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

        try:
            encrypted_payload = self._encrypt_log_data(log_data)
            print(encrypted_payload)
            response = requests.post(self.logstash_url, json=encrypted_payload, verify=False, timeout=5)
            response.raise_for_status()
            print(f"Log ECS chiffré envoyé (Séquence: {self.sequence-1})")
        except Exception as e:
            print(f"Erreur lors de l'envoi du log à Logstash: {e}")
        
        #return valid_hash
