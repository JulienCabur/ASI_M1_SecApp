import datetime
import os
import requests
import hashlib
import urllib3

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
            response = requests.post(self.logstash_url, json=log_data, verify=False, timeout=5)
            print(f"Log ECS envoyé - Action: {action}")
        except Exception as e:
            print(f"Erreur lors de l'envoi du log à Logstash: {e}")
        
        #return valid_hash
