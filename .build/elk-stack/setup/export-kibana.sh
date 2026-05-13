#!/usr/bin/env bash
# Export Kibana Data Views, Rules and Actions to kibana_export.ndjson
# Usage: ELASTIC_PASSWORD="password" bash export-kibana.sh

set -uo pipefail

ELASTIC_PASSWORD="${ELASTIC_PASSWORD:-}"
KIBANA_URL="https://localhost:5601"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FINAL_OUTPUT="${SCRIPT_DIR}/kibana_export.ndjson"

# Write to /tmp first to avoid curl path issues on Windows (spaces, accents, etc.)
TMP_OUTPUT="$(mktemp /tmp/kib_export_XXXXXX.ndjson)"

if [[ -z "$ELASTIC_PASSWORD" ]]; then
  echo "[x] Set ELASTIC_PASSWORD before running this script."
  exit 1
fi

# If the output path ended up as a directory from a previous failed run, remove it
if [[ -d "$FINAL_OUTPUT" ]]; then
  echo "[!] Found a directory at ${FINAL_OUTPUT}, removing it."
  rm -rf "$FINAL_OUTPUT"
fi

CURL_OPTS=(-s --insecure -u "elastic:${ELASTIC_PASSWORD}")

echo "[+] Checking connection to Kibana (${KIBANA_URL})..."
curl_exit=0
http_code=$(curl "${CURL_OPTS[@]}" \
  -o /tmp/kib_status.json \
  -w "%{http_code}" \
  "${KIBANA_URL}/api/status") || curl_exit=$?

if [[ $curl_exit -ne 0 ]]; then
  echo "[x] Connection failed (curl exit ${curl_exit}). Is Kibana running?"
  exit 1
fi
if [[ "$http_code" != "200" ]]; then
  echo "[x] HTTP ${http_code} — wrong password or Kibana not ready."
  cat /tmp/kib_status.json
  exit 1
fi
echo "    Kibana OK (HTTP 200)."

echo "[+] Exporting Data Views, Rules and Actions..."
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
  echo "[x] Export failed (curl=${curl_exit}, HTTP=${http_export})."
  cat "${TMP_OUTPUT}" 2>/dev/null || true
  rm -f "${TMP_OUTPUT}"
  exit 1
fi

count=$(wc -l < "${TMP_OUTPUT}")
if [[ "$count" -eq 0 ]]; then
  echo "[!] Empty file — no objects found (did you create any Data Views or Rules in Kibana?)."
  rm -f "${TMP_OUTPUT}"
  exit 1
fi

cp "${TMP_OUTPUT}" "${FINAL_OUTPUT}"
rm -f "${TMP_OUTPUT}"

echo "[+] Export done: ${count} objects -> ${FINAL_OUTPUT}"
echo "[+] Don't forget to commit this file."
