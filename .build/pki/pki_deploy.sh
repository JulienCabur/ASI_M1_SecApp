#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

BASE_DIR="/etc/pki/CA"
EXPORT_DIR="/export/certs"
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

# Signing CA
mkdir -p $BASE_DIR/signing-ca/{private,db,certs}
chmod 700 $BASE_DIR/signing-ca/private

touch $BASE_DIR/signing-ca/db/signing-ca.db
touch $BASE_DIR/signing-ca/db/signing-ca.db.attr
echo 01 > $BASE_DIR/signing-ca/db/signing-ca.crt.srl
echo 01 > $BASE_DIR/signing-ca/db/signing-ca.crl.srl

openssl req -new -config $CONFIG_DIR/signing-ca.conf \
    -out $BASE_DIR/signing-ca.csr \
    -keyout $BASE_DIR/signing-ca/private/signing-ca.key \
    -passout env:SIGNING_PASS \
    -batch

openssl ca -config $CONFIG_DIR/root-ca.conf \
    -in $BASE_DIR/signing-ca.csr \
    -out $BASE_DIR/signing-ca/certs/signing-ca.crt \
    -extensions signing_ca_ext \
    -passin env:ROOT_PASS \
    -batch

# Chain of trust
cat $BASE_DIR/signing-ca/certs/signing-ca.crt $BASE_DIR/root-ca/certs/root-ca.crt > $EXPORT_DIR/ca-chain.pem
cp $BASE_DIR/signing-ca/certs/signing-ca.crt $EXPORT_DIR/signing-ca.crt
chmod 644 $EXPORT_DIR/ca-chain.pem $EXPORT_DIR/signing-ca.crt