openssl req -new -config /etc/pki/CA/config/identity.conf \
    -out docteur_martin.csr \
    -keyout docteur_martin.key \
    -nodes

# On définit l'autorité qui signe (Signing CA 1)
export ca="signing-ca1"

openssl ca -config /etc/pki/CA/config/signing-ca.conf \
    -in docteur_martin.csr \
    -out docteur_martin.crt \
    -extensions email_ext \
    -passin env:SIGNING1_PASS \
    -batch

openssl pkcs12 -export \
    -in docteur_martin.crt \
    -inkey docteur_martin.key \
    -certfile /etc/pki/CA/certs/ca-chain.pem \
    -name "Certificat Docteur Martin" \
    -out docteur_martin.p12 \
    -passout pass:password_docteur

cp docteur_martin.p12 /etc/pki/CA/config