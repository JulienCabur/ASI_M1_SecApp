openssl req -new -config identity.conf \
    -out docteur_martin.csr \
    -keyout docteur_martin.key \
    -nodes # On génère une clé sans mot de passe pour simplifier l'export PKCS12 après

    # On définit l'autorité de signature
export ca="signing-ca1"

openssl ca -config signing-ca.conf \
    -in docteur_martin.csr \
    -out docteur_martin.crt \
    -extensions email_ext \
    -passin env:SIGNING1_PASS \
    -batch

openssl pkcs12 -export \
    -in docteur_martin.crt \
    -inkey docteur_martin.key \
    -certfile /etc/pki/CA/certs/ca-chain.pem \
    -name "Certificat Identité - Dr Martin" \
    -out docteur_martin.p12 \
    -passout pass:password_docteur # Mot de passe que le docteur devra taper pour l'importer