"""Test E2E du flow de login par certificat.

Reproduit côté client ce que fait le navigateur :
  1. GET  /auth/cert/login/challenge?username=...
  2. Signe `${nonce}:${timestamp}` avec la clé privée du .p12 (RSA-PSS / SHA-256, MAX salt)
  3. POST /auth/cert/login/proof avec la signature + cert PEM
  4. Vérifie qu'on récupère un `authorize_url` Keycloak
     ET que le cookie `secuapp_oidc_state` a bien été posé.

On NE suit PAS le redirect vers Keycloak — ce script s'arrête juste avant,
puisque la suite (échange code, callback, binding cert↔preferred_username)
nécessite un vrai navigateur authentifié sur Keycloak.

Usage : placer dr_level.p12 + adapter le mdp en bas, puis `python test_cert_login.py`.
"""
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

BASE_URL = "http://localhost:8081"
USERNAME = "dr_level"
P12_FILE = "dr_level.p12"
P12_PASSWORD = "aUaIAh682QpaB1M/U/5WuXc3KFMIRYzA"
REDIRECT_TO = "/dashboard"


def test_cert_login_flow() -> None:
    session = requests.Session()

    print(f"[1/3] GET /auth/cert/login/challenge?username={USERNAME}")
    resp = session.get(f"{BASE_URL}/auth/cert/login/challenge", params={"username": USERNAME})
    if resp.status_code != 200:
        print(f"   [KO] challenge: {resp.status_code} {resp.text}")
        return
    challenge = resp.json()
    nonce, timestamp = challenge["nonce"], challenge["timestamp"]
    print(f"   nonce={nonce}\n   timestamp={timestamp}")

    print("[2/3] Signature locale du challenge avec le .p12")
    try:
        with open(P12_FILE, "rb") as f:
            p12_data = f.read()
        private_key, cert, _ = pkcs12.load_key_and_certificates(
            p12_data, P12_PASSWORD.encode(), default_backend()
        )
    except Exception as e:
        print(f"   [KO] lecture .p12 : {e}")
        return

    message = f"{nonce}:{timestamp}".encode()
    signature = private_key.sign(
        message,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    print(f"   signature_hex={signature.hex()[:40]}... ({len(signature)} bytes)")

    print("[3/3] POST /auth/cert/login/proof")
    payload = {
        "username": USERNAME,
        "nonce": nonce,
        "timestamp": timestamp,
        "signature": signature.hex(),
        "certificate": cert_pem,
        "redirect_to": REDIRECT_TO,
    }
    resp = session.post(f"{BASE_URL}/auth/cert/login/proof", json=payload)
    if resp.status_code != 200:
        print(f"   [KO] proof : {resp.status_code} {resp.text}")
        return

    body = resp.json()
    print(f"   authorize_url = {body.get('authorize_url')}")

    state_cookie = session.cookies.get("secuapp_oidc_state")
    if not state_cookie:
        print("   [KO] cookie secuapp_oidc_state absent — le binding cert ne survivra pas au callback")
        return
    print(f"   secuapp_oidc_state posé ({len(state_cookie)} chars, httpOnly)")

    print("\n[OK] Flow cert-login validé jusqu'au redirect Keycloak.")
    print("     Étapes restantes (navigateur réel uniquement) : redirect → Keycloak → /auth/callback.")


def test_username_mismatch() -> None:
    """Vérifie que le binding CN↔username est bien appliqué : on revendique
    un username différent du CN du cert, le proof doit être rejeté."""
    print("\n--- Test négatif : username ≠ CN du cert ---")
    session = requests.Session()
    fake_username = "dr_other"
    resp = session.get(f"{BASE_URL}/auth/cert/login/challenge", params={"username": fake_username})
    if resp.status_code != 200:
        print(f"   challenge fake user : {resp.status_code} (attendu si user inexistant en DB)")
        return
    nonce = resp.json()["nonce"]
    timestamp = resp.json()["timestamp"]

    with open(P12_FILE, "rb") as f:
        p12_data = f.read()
    private_key, cert, _ = pkcs12.load_key_and_certificates(p12_data, P12_PASSWORD.encode(), default_backend())
    message = f"{nonce}:{timestamp}".encode()
    signature = private_key.sign(
        message,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    payload = {
        "username": fake_username,
        "nonce": nonce,
        "timestamp": timestamp,
        "signature": signature.hex(),
        "certificate": cert.public_bytes(serialization.Encoding.PEM).decode(),
        "redirect_to": "/",
    }
    resp = session.post(f"{BASE_URL}/auth/cert/login/proof", json=payload)
    if resp.status_code == 400:
        print(f"   [OK] proof rejeté (400) — binding CN↔username fonctionne")
    else:
        print(f"   [KO] proof accepté avec un username falsifié ! status={resp.status_code}")


if __name__ == "__main__":
    test_cert_login_flow()
    test_username_mismatch()
