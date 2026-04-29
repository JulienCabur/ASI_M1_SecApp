import requests
import hashlib
import datetime
from service.log_service import LogsService

LOGSTASH_URL = "https://localhost:5044"

logservice = LogsService()

def generate_log(action, sequence, prev_hash, patient_id="null", is_falsified=False):
    # 1. On fige toutes les variables (y compris l'heure exacte) AVANT le hachage
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    log_level = "CRITICAL" if action == "DELETE_DOSSIER" else "INFO"
    service_name = "backend_python"
    user_id = "doc-123"
    user_role = "MEDECIN"
    source_ip = "192.168.1.50"
    
    # 2. Concaténation stricte de TOUS les champs (sauf le message et le hash lui-même)
    # L'ordre doit être absolu : timestamp + log_level + service_name + action + user_id + user_role + source_ip + patient_id + sequence + prev_hash
    raw_string = f"{timestamp}{log_level}{service_name}{action}{user_id}{user_role}{source_ip}{patient_id}{sequence}{prev_hash}"
    
    valid_hash = hashlib.sha256(raw_string.encode('utf-8')).hexdigest()
    
    # Falsification volontaire pour le test (si demandé)
    final_hash = "111111hashfalsifie222222333333" if is_falsified else valid_hash

    # 3. Construction du dictionnaire au format ECS (avec les catégories métier)
    log_data = {
        "@timestamp": timestamp,
        "log": {
            "level": log_level
        },
        "service": {
            "name": service_name
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
            "ip": source_ip
        },
        "patient": {
            "id": patient_id
        },
        "audit_chain": {
            "sequence": sequence,
            "hash": final_hash,
            "previous_hash": prev_hash
        }
    }
    
    # 4. Envoi asynchrone à Logstash
    try:
        logservice.public_cert_path = "../../.build/secrets/logstash/server.crt"  # Assurez-vous que le chemin est correct
        log_encrypted = logservice._encrypt_log_data(log_data)  # Simule le chiffrement pour tester la partie de déchiffrement dans Logstash
        response = requests.post(LOGSTASH_URL, json=log_encrypted, verify=False, timeout=5)
        etat = "😈 FALSIFIÉ" if is_falsified else "✅ Valide"
        print(f"Log ECS (Full Hashing) envoyé ({etat}) - Action: {action}")
    except Exception as e:
        print(f"Erreur de connexion à Logstash : {e}")

    return valid_hash

if __name__ == "__main__":
    print("🚀 Début de la simulation d'envoi de logs...")
    
    # Génération d'une chaîne de 3 logs (le dernier est une attaque)
    hash1 = generate_log("AUTH_SUCCESS", 101, "0000000000000000000000000000000000000000000000000000000000000000")
    hash2 = generate_log("PATIENT_DATA_ACCESS", 102, hash1, "pat-999")
    hash3 = generate_log("DELETE_DOSSIER", 103, hash2, "pat-999", is_falsified=True)