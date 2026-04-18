from sqlalchemy.orm import Session
from schema.auth_schema import UserInDB, CertificateRequest
from keycloak import KeycloakAdmin
from dotenv import load_dotenv
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
import os

load_dotenv()  # Charger les variables d'environnement depuis le fichier .env
class AuthService:
    """
    Classe pour gérer les opérations liées à l'authentification.
    """
    def __init__(self, db: Session):
        """
        Initialise le service de gestion de l'authentification avec une session de base de données.
        :param db: Session de base de données SQLAlchemy.
        """
        self.db = db
        self.csr_repository = "/app/csr"
        self.cert_repository = "/app/certs_doctors"
    
    def generate_csr(self, common_name: str):
        file_csr = common_name + ".csr"
        file_key = common_name + ".key"

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())

        subject = x509.Name([
            x509.NameAttribute(NameOID.DOMAIN_COMPONENT, "be"),
            x509.NameAttribute(NameOID.DOMAIN_COMPONENT, "healthapp"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Health Application"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name)
        ])

        csr = x509.CertificateSigningRequestBuilder().subject_name(subject).sign(private_key, SHA256(), default_backend())

        with open(os.path.join(self.csr_repository, file_csr), "wb") as f:
            f.write(csr.public_bytes(serialization.Encoding.PEM))

        with open(os.path.join(self.csr_repository, file_key), "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
        return f"CSR et clé privée générés pour {common_name}"
    
    def check_csr_signed(self, common_name: str):
        path=self.cert_repository + "/" + common_name + ".p12"
        if not os.path.exists(path):
            raise Exception("Certificat non trouvé")
        return path
    
    def create_doctor_in_keycloak(self, cert_path: str, user_info: CertificateRequest) -> str:
        with open(cert_path, "rb") as f:
            cert_data = f.read()

        with open(self.cert_repository + "/" + user_info.username + ".p12password", "r") as f:
            p12_password = f.read().strip()

        private_key, cert, additional_certs = pkcs12.load_key_and_certificates(cert_data, p12_password.encode())
        serial_hex = f"{cert.serial_number:02X}"
    
        print(f"Création de l'utilisateur dans Keycloak avec le certificat: {cert_path}, numéro de série: {serial_hex}")

        keycloak_admin = KeycloakAdmin(
            server_url=os.getenv("KEYCLOAK_SERVER_URL"),
            username=os.getenv("KEYCLOAK_ADMIN"),
            password=os.getenv("KEYCLOAK_ADMIN_PASSWORD"),
            realm_name=os.getenv("KEYCLOAK_REALM"),
            user_realm_name="master",
            verify=False
        )

        user_payload = {
            "email": user_info.email,
            "username": user_info.username,
            "enabled": True,
            "firstName": user_info.first_name,
            "lastName": user_info.last_name,
            "groups": ["/Docteurs"],
            "attributes": {
                "certificate_serial": serial_hex,
                "user_type": "doctor"
            }
        }

        try:
            new_user_id = keycloak_admin.create_user(user_payload, exist_ok=False)
            group_patient = keycloak_admin.get_group_by_path("/Patients")
            keycloak_admin.group_user_remove(new_user_id, group_patient['id'])
            keycloak_admin.update_user(
                user_id=new_user_id,
                payload={
                    "requiredActions": ["VERIFY_EMAIL", "CONFIGURE_TOTP"]
                }
            )
            return p12_password
        except Exception as e:
            raise Exception(f"Erreur lors de la création de l'utilisateur dans Keycloak: {str(e)}")
    
    def get_password_for_cert(self, username: str) -> str:
        password_path = os.path.join(self.cert_repository, username + ".p12password")
        if not os.path.exists(password_path):
            raise Exception("Mot de passe pour le certificat non trouvé")
        with open(password_path, "r") as f:
            return f.read().strip()

    def delete_sensitive_files(self, common_name: str):
        csr_path = os.path.join(self.csr_repository, common_name + ".csr")
        csr_password_path = os.path.join(self.csr_repository, common_name + ".csrpassword")
        crt_path = os.path.join(self.cert_repository, common_name + ".p12")
        crt_password_path = os.path.join(self.cert_repository, common_name + ".p12password")
        key_path = os.path.join(self.csr_repository, common_name + ".key")
        
        for path in [csr_path, crt_path, key_path, csr_password_path, crt_password_path]:
             if os.path.exists(path):
                os.remove(path)
