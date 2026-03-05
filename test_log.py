import requests
import hashlib
import json
from datetime import datetime, timezone

# 1. Configuration de l'adresse de ton Logstash
LOGSTASH_URL = "http://localhost:5044"

# 2. Création du contenu du log avec le NOUVEAU format de date
log_data = {
    # Génère une date parfaite pour Elasticsearch : ex: "2026-03-05T10:22:42.123Z"
    "@timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    "sequence_number": 1,
    "previous_hash": "0000000000000000000000000000000000000000000000000000000000000000",
    "level": "INFO",
    "action": "PATIENT_DATA_ACCESS",
    "user_role": "MEDECIN",
    "message": "Consultation du dossier médical."
}

# 3. Le cœur de la sécurité : Calcul du hash cryptographique
# On transforme le dictionnaire en texte (trié pour être toujours identique)
log_string = json.dumps(log_data, sort_keys=True).encode('utf-8')
# On calcule l'empreinte SHA-256
current_hash = hashlib.sha256(log_string).hexdigest()

# On ajoute le hash calculé au log final
log_data["hash"] = current_hash

# 4. Envoi du log au format JSON
print(f"Préparation de l'envoi du log n°{log_data['sequence_number']}...")
print(f"Date générée : {log_data['@timestamp']}")
print(f"Hash calculé : {current_hash}")

try:
    response = requests.post(LOGSTASH_URL, json=log_data)
    
    # Logstash renvoie un code 200 (OK) si tout s'est bien passé
    if response.status_code == 200:
        print("✅ Succès ! Le log a été accepté par Logstash.")
    else:
        print(f"❌ Erreur {response.status_code} : {response.text}")
        
except requests.exceptions.ConnectionError:
    print("❌ Erreur de connexion : Logstash tourne-t-il bien sur le port 5044 ?")