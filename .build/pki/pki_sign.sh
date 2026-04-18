#!/bin/bash

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
            
            openssl ca -config /etc/pki/CA/config/signing-ca.conf \
                -in $csr \
                -out $PATH_CERT/$name.crt \
                -extensions email_ext \
                -passin env:SIGNING1_PASS \
                -batch
            
            echo "Certificate generated at: $PATH_CERT/$name.crt"
            
            echo "Exporting certificate to PKCS#12 format..."
            p12password=$(openssl rand -base64 24 | tr -d '=' | cut -c1-32)

            openssl pkcs12 -export \
                -in $PATH_CERT/$name.crt \
                -inkey $PATH_CSR/$name.key \
                -certfile /etc/pki/CA/certs/ca-chain.pem \
                -name "Certificat Docteur $name" \
                -out $PATH_CERT/$name.p12 \
                -passout pass:"$p12password"

            echo "PKCS#12 file generated at: $PATH_CERT/$name.p12 with password: $p12password"

            echo "$p12password" > $PATH_CERT/$name.p12password

            echo "Certificate for $name processed successfully. Password stored at: $PATH_CERT/$name.p12password"

            rm $PATH_CSR/$name.csr
            rm $PATH_CSR/$name.key
            rm $PATH_CERT/$name.crt
        done
    fi
done