#!/bin/bash
# Kibana bootstrap — starts Kibana in the background, waits for the API,
# imports saved objects if an export file is present, then keeps the
# process in the foreground (same idea as Keycloak --import-realm).

set -eo pipefail

IMPORT_FILE="${IMPORT_FILE:-/kibana_export.ndjson}"
KIBANA_URL="https://localhost:5601"
CACERT="/usr/share/kibana/config/certs/ca-chain.pem"

log() { echo "[kibana-bootstrap] $1"; }

/usr/local/bin/kibana-docker &
KIBANA_PID=$!

if [[ ! -f "$IMPORT_FILE" ]]; then
    log "No import file at ${IMPORT_FILE}, skipping."
    wait $KIBANA_PID
    exit $?
fi

log "Waiting for Kibana API to come up..."
kibana_ready=0
for _ in $(seq 1 60); do
    level=$(curl -sf --cacert "${CACERT}" \
        -u "elastic:${ELASTIC_PASSWORD}" \
        "${KIBANA_URL}/api/status" 2>/dev/null \
        | grep -o '"level":"[^"]*"' | head -1 || true)

    if [[ "$level" == '"level":"available"' ]]; then
        kibana_ready=1
        break
    fi
    sleep 5
done

if (( kibana_ready )); then
    log "Kibana is ready. Importing objects from ${IMPORT_FILE}..."
    result=$(curl -sf --cacert "${CACERT}" \
        -u "elastic:${ELASTIC_PASSWORD}" \
        -X POST "${KIBANA_URL}/api/saved_objects/_import?overwrite=true" \
        -H "kbn-xsrf: true" \
        --form "file=@${IMPORT_FILE}" 2>/dev/null || echo '{"error":"import curl failed"}')
    if echo "$result" | grep -q '"errors":true'; then
        log "WARNING: some objects failed to import: $result"
    else
        log "Import done."
    fi
else
    log "WARNING: Kibana didn't come up in time, skipping import."
fi

wait $KIBANA_PID
