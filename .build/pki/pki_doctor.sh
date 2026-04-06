#!/bin/bash

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: $0 <name> <password>"
    echo "Erreur: Le nom et le mot de passe doivent être fournis en paramètres."
    exit 1
fi

NAME="$1"
PASSWORD="$2"

openssl req -new -config /etc/pki/CA/config/identity.conf \
    -out docteur_$NAME.csr \
    -keyout docteur_$NAME.key \
    -passout pass:$PASSWORD

# On définit l'autorité qui signe (Signing CA 1)
export ca="signing-ca1"

openssl ca -config /etc/pki/CA/config/signing-ca.conf \
    -in docteur_$NAME.csr \
    -out docteur_$NAME.crt \
    -extensions email_ext \
    -passin env:SIGNING1_PASS \
    -batch

openssl pkcs12 -export \
    -in docteur_$NAME.crt \
    -inkey docteur_$NAME.key \
    -certfile /etc/pki/CA/certs/ca-chain.pem \
    -name "Certificat Docteur $NAME" \
    -out docteur_$NAME.p12 \
    -passout pass:$PASSWORD