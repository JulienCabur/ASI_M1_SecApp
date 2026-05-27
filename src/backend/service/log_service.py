import datetime
import time
import os
import json
import httpx
import hashlib
import base64
import asyncio
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.backends import default_backend

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
        self.logstash_healthcheck = os.getenv("LOGSTASH_HEALTHCHECK", "http://logstash:9600/_health_report")
        self.service_name = service_name
        self.previous_hash = "0000000000000000000000000000000000000000000000000000000000000000"
        self.source_ip = "0.0.0.0"
        self.public_cert_path = "/app/certs/logstash.crt"

        self.session_key = None
        self.encrypted_session_key_b64 = None
        self.session_id = None
        self.session_creation_time = 0
        self.session_rotation_interval = 300

        self._health_cache_result=False
        self._health_cache_time= 0
        self._HEALTH_CACHE_TTL= 10

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

    async def health_check(self) -> bool:
        """
        Vérifie la santé du service de logs avec un cache TTL pour éviter
        de saturer logstash (ou d'attendre le timeout) à chaque requête.
        """
        now = time.time()
        if now - self._health_cache_time < self._HEALTH_CACHE_TTL:
            return self._health_cache_result
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(self.logstash_healthcheck)
            result = response.status_code == 200 and response.json().get("status") not in ("red", "unknown")
        except Exception as e:
            print(f"Erreur lors de la vérification de la santé du service de logs: {e}")
            result = False
        self._health_cache_result = result
        self._health_cache_time = now
        return result

    async def add_logs(self, action: str, log_level: str, user_id: str, user_role: str, patient_id: str = "null"):
        """
        Enregistre un log : calcule la chaîne d'audit de façon synchrone,
        puis délègue l'envoi réseau en arrière-plan pour ne pas bloquer la requête.
        """
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

        raw_string = f"{timestamp}{log_level}{self.service_name}{action}{user_id}{user_role}{user_role}{self.source_ip}{patient_id}{self.sequence}{self.previous_hash}"
        valid_hash = hashlib.sha256(raw_string.encode('utf-8')).hexdigest()

        log_data = {
            "@timestamp": timestamp,
            "log": {"level": log_level},
            "service": {"name": self.service_name},
            "message": f"Action {action} effectuée par l'utilisateur.",
            "event": {"action": action},
            "user": {"id": user_id, "roles": [user_role]},
            "source": {"ip": self.source_ip},
            "patient": {"id": patient_id},
            "audit_chain": {
                "sequence": self.sequence,
                "hash": valid_hash,
                "previous_hash": self.previous_hash
            }
        }

        self.previous_hash = valid_hash
        self.sequence += 1

        task = asyncio.create_task(self._send_log(log_data, timestamp, log_level, action, user_id, patient_id, valid_hash))
        task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

    async def _send_log(self, log_data: dict, timestamp: str, log_level: str, action: str, user_id: str, patient_id: str, valid_hash: str):
        sequence = log_data["audit_chain"]["sequence"]
        try:
            encrypted_payload = self._encrypt_log_data(log_data)

            if await self.health_check():
                if os.path.exists("/app/logs/temp_logs.log"):
                    with open("/app/logs/temp_logs.log", "r") as temp_log_file:
                        pending = [line.strip() for line in temp_log_file if line.strip()]
                    os.remove("/app/logs/temp_logs.log")
                    async with httpx.AsyncClient(verify=False) as client:
                        for raw in pending:
                            try:
                                await client.post(self.logstash_url, json=json.loads(raw))
                            except Exception as e:
                                print(f"Erreur flush log temporaire: {e}")
                async with httpx.AsyncClient(verify=False, timeout=5) as client:
                    response = await client.post(self.logstash_url, json=encrypted_payload)
                    response.raise_for_status()
                print(f"Log ECS chiffré envoyé (Séquence: {sequence})")
            else:
                if not os.path.exists("/app/logs/"):
                    os.makedirs("/app/logs/")
                with open("/app/logs/temp_logs.log", "a+") as temp_log_file:
                    temp_log_file.write(json.dumps(encrypted_payload) + "\n")

            if not os.path.exists("/app/logs/"):
                os.makedirs("/app/logs/")
            with open("/app/logs/local_logs.log", "a+") as log_file:
                log_file.write(f"{timestamp} - {log_level} - {action} - User: {user_id} - Patient: {patient_id} - Sequence: {sequence} - Hash: {valid_hash}\n")
        except Exception as e:
            print(f"Erreur lors de l'envoi du log à Logstash: {e}")
