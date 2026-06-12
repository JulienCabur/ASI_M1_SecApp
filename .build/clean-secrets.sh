DEFAULT_PATH=$(dirname "$(realpath "$0")")
echo "Cleaning secrets files from secrets folder but keeping subfolders..."
find "$DEFAULT_PATH/secrets" -type f -delete
echo "Done!"