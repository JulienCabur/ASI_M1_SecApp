#!/bin/bash

DEFAULT_PATH=$(dirname "$(realpath "$0")")

echo "Creating .env files..."

# .build/.env
if [ ! -f "$DEFAULT_PATH/.env" ]; then
    cp "$DEFAULT_PATH/env.example" "$DEFAULT_PATH/.env"
    echo "Created $DEFAULT_PATH/.env"
else
    echo "$DEFAULT_PATH/.env already exists"
fi

echo "Done!"