#!/usr/bin/env bash
# Export Kibana Data Views + Rules vers kibana_export.ndjson
# Usage : ELASTIC_PASSWORD="motdepasse" bash export-kibana.sh

set -uo pipefail

ELASTIC_PASSWORD="${ELASTIC_PASSWORD:-}"
KIBANA_URL="https://localhost:5601"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FINAL_OUTPUT="${SCRIPT_DIR}/kibana_export.ndjson"

# On écrit d'abord dans /tmp (chemin court, sans accents ni espaces) pour éviter les bugs de curl sur Windows avec les chemins complexes.
TMP_OUTPUT="$(mktemp /tmp/kib_export_XXXXXX.ndjson)"

if [[ -z "$ELASTIC_PASSWORD" ]]; then
  echo "[x] Définis ELASTIC_PASSWORD avant de lancer le script."
  exit 1
fi

# Sécurité : si kibana_export.ndjson existe en tant que répertoire (artefact d'un échec précédent), on l'efface pour ne pas bloquer le cp final.
if [[ -d "$FINAL_OUTPUT" ]]; then
  echo "[!] Répertoire parasite détecté, suppression : ${FINAL_OUTPUT}"
  rm -rf "$FINAL_OUTPUT"
fi

CURL_OPTS=(-s --insecure -u "elastic:${ELASTIC_PASSWORD}")

# Vérification connexion
echo "[+] Vérification de la connexion à Kibana (${KIBANA_URL})..."
curl_exit=0
http_code=$(curl "${CURL_OPTS[@]}" \
  -o /tmp/kib_status.json \
  -w "%{http_code}" \
  "${KIBANA_URL}/api/status") || curl_exit=$?

if [[ $curl_exit -ne 0 ]]; then
  echo "[x] Connexion impossible (curl exit ${curl_exit}). Kibana est-il démarré ?"
  exit 1
fi
if [[ "$http_code" != "200" ]]; then
  echo "[x] HTTP ${http_code} — mauvais mot de passe ou Kibana pas prêt."
  cat /tmp/kib_status.json
  exit 1
fi
echo "    Kibana OK (HTTP 200)."

# Export 
echo "[+] Export des Data Views, Rules et Actions..."
curl_exit=0
http_export=$(curl "${CURL_OPTS[@]}" \
  -X POST "${KIBANA_URL}/api/saved_objects/_export" \
  -H "kbn-xsrf: true" \
  -H "Content-Type: application/json" \
  -d '{
    "type": ["index-pattern", "alert", "action"],
    "includeReferencesDeep": true,
    "excludeExportDetails": false
  }' \
  -o "${TMP_OUTPUT}" \
  -w "%{http_code}") || curl_exit=$?

if [[ $curl_exit -ne 0 || "$http_export" != "200" ]]; then
  echo "[x] Export échoué (curl=${curl_exit}, HTTP=${http_export})."
  cat "${TMP_OUTPUT}" 2>/dev/null || true
  rm -f "${TMP_OUTPUT}"
  exit 1
fi

count=$(wc -l < "${TMP_OUTPUT}")
if [[ "$count" -eq 0 ]]; then
  echo "[!] Fichier vide — aucun objet trouvé (Data View / Rule créés dans Kibana ?)."
  rm -f "${TMP_OUTPUT}"
  exit 1
fi

# Copie vers la destination finale
cp "${TMP_OUTPUT}" "${FINAL_OUTPUT}"
rm -f "${TMP_OUTPUT}"

echo "[+] Export terminé : ${count} objets → ${FINAL_OUTPUT}"
echo "[+] Ajoute ce fichier au commit git."
