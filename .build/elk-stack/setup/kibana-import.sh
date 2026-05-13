#!/usr/bin/env bash

set -eu
set -o pipefail

KIBANA_URL="https://${KIBANA_HOST:-kibana}:5601"
IMPORT_FILE="${IMPORT_FILE:-/kibana_export.ndjson}"
CACERT="${CACERT:-/certs/ca-chain.pem}"

log()    { echo "[+] $1"; }
sublog() { echo "    > $1"; }
suberr() { echo "    ! $1" >&2; }

log "Waiting for Kibana at ${KIBANA_URL}..."

declare -i kibana_ready=0
for _ in $(seq 1 60); do
    level=$(curl -sf --cacert "${CACERT}" -u "elastic:${ELASTIC_PASSWORD}" \
        "${KIBANA_URL}/api/status" 2>/dev/null \
        | grep -o '"level":"[^"]*"' | head -1 || true)

    if [[ "$level" == '"level":"available"' ]]; then
        kibana_ready=1
        break
    fi
    sleep 5
done

if (( !kibana_ready )); then
    suberr "Kibana did not become available within the timeout."
    exit 1
fi

sublog "Kibana is ready."

log "Importing saved objects from ${IMPORT_FILE}..."

declare -i http_code
http_code=$(curl -sf --cacert "${CACERT}" \
    -u "elastic:${ELASTIC_PASSWORD}" \
    -X POST "${KIBANA_URL}/api/saved_objects/_import?overwrite=true" \
    -H "kbn-xsrf: true" \
    --form "file=@${IMPORT_FILE}" \
    -o /tmp/kibana_import_result.json \
    -w "%{http_code}" || echo 0)

if (( http_code == 200 )); then
    sublog "Import successful."
    # partial failures still return 200, so check the body
    if grep -q '"errors":true' /tmp/kibana_import_result.json 2>/dev/null; then
        suberr "Some objects failed to import:"
        cat /tmp/kibana_import_result.json >&2
        exit 1
    fi
else
    suberr "Import failed (HTTP ${http_code}):"
    cat /tmp/kibana_import_result.json >&2
    exit 1
fi

log "Kibana configuration imported successfully."
