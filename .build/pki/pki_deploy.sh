#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

BASE_DIR="/etc/pki/CA"
EXPORT_DIR="/etc/pki/CA/certs"
CONFIG_DIR="/etc/pki/CA/config"

# Preparation
apt update && apt install -y openssl

mkdir -p $EXPORT_DIR
# Root CA
mkdir -p $BASE_DIR/root-ca/{private,db,certs}
chmod 700 $BASE_DIR/root-ca/private

touch $BASE_DIR/root-ca/db/root-ca.db
touch $BASE_DIR/root-ca/db/root-ca.db.attr
echo 01 > $BASE_DIR/root-ca/db/root-ca.crt.srl
echo 01 > $BASE_DIR/root-ca/db/root-ca.crl.srl

openssl req -new -config $CONFIG_DIR/root-ca.conf \
    -out $BASE_DIR/root-ca.csr \
    -keyout $BASE_DIR/root-ca/private/root-ca.key \
    -passout env:ROOT_PASS \
    -batch

openssl ca -config $CONFIG_DIR/root-ca.conf \
    -in $BASE_DIR/root-ca.csr \
    -out $BASE_DIR/root-ca/certs/root-ca.crt \
    -keyfile $BASE_DIR/root-ca/private/root-ca.key \
    -passin env:ROOT_PASS \
    -batch \
    -selfsign \
    -extensions root_ca_ext

# Signing CA 1
mkdir -p $BASE_DIR/signing-ca1/{private,db,certs}
chmod 700 $BASE_DIR/signing-ca1/private

touch $BASE_DIR/signing-ca1/db/signing-ca1.db
touch $BASE_DIR/signing-ca1/db/signing-ca1.db.attr
echo 01 > $BASE_DIR/signing-ca1/db/signing-ca1.crt.srl
echo 01 > $BASE_DIR/signing-ca1/db/signing-ca1.crl.srl

export ca="signing-ca1"
openssl req -new -config $CONFIG_DIR/signing-ca.conf \
    -out $BASE_DIR/signing-ca1.csr \
    -keyout $BASE_DIR/signing-ca1/private/signing-ca1.key \
    -passout env:SIGNING1_PASS \
    -batch

openssl ca -config $CONFIG_DIR/root-ca.conf \
    -in $BASE_DIR/signing-ca1.csr \
    -out $BASE_DIR/signing-ca1/certs/signing-ca1.crt \
    -extensions signing_ca_ext \
    -passin env:ROOT_PASS \
    -batch

# Signing CA 2
mkdir -p $BASE_DIR/signing-ca2/{private,db,certs}
chmod 700 $BASE_DIR/signing-ca2/private

touch $BASE_DIR/signing-ca2/db/signing-ca2.db
touch $BASE_DIR/signing-ca2/db/signing-ca2.db.attr
echo 01 > $BASE_DIR/signing-ca2/db/signing-ca2.crt.srl
echo 01 > $BASE_DIR/signing-ca2/db/signing-ca2.crl.srl

export ca="signing-ca2"
openssl req -new -config $CONFIG_DIR/signing-ca.conf \
    -out $BASE_DIR/signing-ca2.csr \
    -keyout $BASE_DIR/signing-ca2/private/signing-ca2.key \
    -passout env:SIGNING2_PASS \
    -batch

openssl ca -config $CONFIG_DIR/root-ca.conf \
    -in $BASE_DIR/signing-ca2.csr \
    -out $BASE_DIR/signing-ca2/certs/signing-ca2.crt \
    -extensions signing_ca_ext \
    -passin env:ROOT_PASS \
    -batch

# Chain of trust
cat $BASE_DIR/signing-ca1/certs/signing-ca1.crt $BASE_DIR/root-ca/certs/root-ca.crt > $EXPORT_DIR/ca-chain.pem
cat $BASE_DIR/signing-ca2/certs/signing-ca2.crt $BASE_DIR/root-ca/certs/root-ca.crt > $EXPORT_DIR/ca-chain2.pem
cp $BASE_DIR/signing-ca1/certs/signing-ca1.crt $EXPORT_DIR/signing-ca1.crt
cp $BASE_DIR/signing-ca2/certs/signing-ca2.crt $EXPORT_DIR/signing-ca2.crt
chmod 644 $EXPORT_DIR/ca-chain.pem $EXPORT_DIR/signing-ca2.crt $EXPORT_DIR/signing-ca1.crt $EXPORT_DIR/ca-chain2.pem

# Generate serveur certificate
openssl req -new -config $CONFIG_DIR/server.conf \
    -out $BASE_DIR/server.csr \
    -keyout $BASE_DIR/server.key \
    -nodes

export ca="signing-ca1"
openssl ca -config $CONFIG_DIR/signing-ca.conf \
    -in $BASE_DIR/server.csr \
    -out $BASE_DIR/server.crt \
    -extensions server_ext \
    -passin env:SIGNING1_PASS \
    -batch

cp $BASE_DIR/server.crt $EXPORT_DIR/server.crt
cp $BASE_DIR/server.key $EXPORT_DIR/server.key

chown 1000:1000 $EXPORT_DIR/server.key
chmod 644 $EXPORT_DIR/server.crt
chmod 600 $EXPORT_DIR/server.key

echo "PKI Deployed"