#!/bin/bash

# Watcher PKI : signe les CSR déposés par le backend dans $PATH_CSR.
# La paire de clés est désormais générée côté navigateur — la PKI ne voit
# JAMAIS la clé privée du médecin. Elle se contente de signer le CSR et
# de déposer le certificat PEM résultant dans $PATH_CERT, à charge pour
# le back de le lire puis de le supprimer.

export ca="signing-ca1"
PATH_CSR="/etc/pki/CA/csr"
PATH_CERT="/etc/pki/CA/certs_doctors"

while true; do

    myarray=(`find $PATH_CSR -maxdepth 1 -type f -name "*.csr"`)

    if [ ${#myarray[@]} -gt 0 ]; then
        for csr in "${myarray[@]}"
        do
            name=$(basename "$csr" .csr)
            echo "Processing CSR: $csr for $name"

            # Signature du CSR navigateur. On écrit d'abord sur un .crt.tmp
            # pour éviter que le back lise un fichier partiellement écrit.
            openssl ca -config /etc/pki/CA/config/signing-ca.conf \
                -in $csr \
                -out $PATH_CERT/$name.crt.tmp \
                -extensions email_ext \
                -passin env:SIGNING1_PASS \
                -batch

            mv $PATH_CERT/$name.crt.tmp $PATH_CERT/$name.crt
            echo "Certificate generated at: $PATH_CERT/$name.crt"

            # Le CSR est consommé ; le .crt est laissé pour que le back le
            # lise (récupération du serial + envoi au navigateur), puis le
            # supprime via `delete_sensitive_files`.
            rm $csr
        done
    fi
    sleep 1
done
