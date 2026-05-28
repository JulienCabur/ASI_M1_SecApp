#!/bin/bash
set -euo pipefail

DEFAULT_PATH=$(dirname "$(realpath "$0")")

echo "Creating .env files..."

# .build/.env
if [ -f "$DEFAULT_PATH/.env" ]; then
    echo "$DEFAULT_PATH/.env already exists. Do you want to overwrite it? (y/n)"
    read -r response
    if [ "$response" = "n" ]; then
        echo "Aborting. $DEFAULT_PATH/.env was not overwritten."
        exit 0
    fi
fi

cp "$DEFAULT_PATH/env.example" "$DEFAULT_PATH/.env"
chmod 600 "$DEFAULT_PATH/.env"

echo "Done!"

exit 0