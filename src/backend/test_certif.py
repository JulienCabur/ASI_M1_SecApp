import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization

BASE_URL = "http://localhost:8081" 
USERNAME = "dr_gatien" # Placer à la racine du projet
P12_FILE = "dr_gatien.p12"
P12_PASSWORD = "pass_généré"

def test_login_flow():
    resp = requests.get(f"{BASE_URL}/auth/challenge", params={"username": USERNAME})
    if resp.status_code != 200:
        print(f"Erreur challenge: {resp.text}")
        return

    challenge_data = resp.json()
    nonce = challenge_data["nonce"]
    timestamp = challenge_data["timestamp"]
    print(f"Nonce: {nonce}\nTimestamp: {timestamp}")
    try:
        with open(P12_FILE, "rb") as f:
            p12_data = f.read()
        private_key, cert, additional_certs = pkcs12.load_key_and_certificates(
            p12_data, 
            P12_PASSWORD.encode(), 
            default_backend()
        )
    except Exception as e:
        print(f"Erreur P12: {e}")
        return
    message = f"{nonce}:{timestamp}".encode()

    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    signature_hex = signature.hex()
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    payload = {
        "username": USERNAME,
        "nonce": nonce,
        "timestamp": timestamp,
        "signature": signature_hex,
        "certificate": cert_pem
    }

    resp = requests.post(f"{BASE_URL}/auth/challenge_response", json=payload)
    if resp.status_code == 200:
        print(f"Réponse du serveur: {resp.json()}")
    else:
        print(f"Failed: {resp.status_code}")
        print(f"Détail: {resp.text}")

if __name__ == "__main__":
    test_login_flow()