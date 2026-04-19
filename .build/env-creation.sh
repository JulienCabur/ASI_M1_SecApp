#!/bin/bash

DEFAULT_PATH=$(dirname "$(realpath "$0")")

echo "Creating .env files..."

# .build/.env
if [ -f "$DEFAULT_PATH/.env" ]; then
    echo "$DEFAULT_PATH/.env already exists. Do you want to overwrite it? (y/n)"
    read response
    if [ "$response" = "y" ]; then
        cp "$DEFAULT_PATH/env.example" "$DEFAULT_PATH/.env"
        echo "Overwritten $DEFAULT_PATH/.env"
        exit 0
    else
        echo "Aborting. $DEFAULT_PATH/.env was not overwritten."
        exit 0
    fi
fi

cp "$DEFAULT_PATH/env.example" "$DEFAULT_PATH/.env"
echo "Created $DEFAULT_PATH/.env"

echo "Done!"

exit 0