
import datetime
import secrets
import time
from sqlalchemy.orm import Session
from schema.auth_schema import UserInDB, CertificateRequest, ChallengeResponse
import base64
from models.auth import User
from keycloak import KeycloakAdmin
from dotenv import load_dotenv
from core.auth import resolve_keycloak_verify
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
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
            verify=resolve_keycloak_verify()
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
            user = User(
                id=new_user_id,
                username=user_info.username,
                roles="doctor",
                challenge_nonce=None
            )
            self.db.add(user)
            self.db.commit()
            
            return p12_password
        except Exception as e:
            self.delete_sensitive_files(user_info.username)
            raise Exception(f"Erreur lors de la création de l'utilisateur dans Keycloak: {str(e)}")
    
    def get_p12_content(self, cert_path: str) -> bytes:
        with open(cert_path, "rb") as f:
            p12_content = base64.b64encode(f.read()).decode('utf-8')
        return p12_content

    def delete_sensitive_files(self, common_name: str):
        csr_path = os.path.join(self.csr_repository, common_name + ".csr")
        csr_password_path = os.path.join(self.csr_repository, common_name + ".csrpassword")
        crt_path = os.path.join(self.cert_repository, common_name + ".p12")
        crt_password_path = os.path.join(self.cert_repository, common_name + ".p12password")
        key_path = os.path.join(self.csr_repository, common_name + ".key")

        for path in [csr_path, crt_path, key_path, csr_password_path, crt_password_path]:
            if os.path.exists(path):
                os.remove(path)

    def generate_challenge(self, username: str) -> ChallengeResponse:
        user = self.db.query(User).filter(User.username == username).first()
        if not user:
            raise Exception("Utilisateur non trouvé")
        nonce = secrets.token_hex(16)
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        user.challenge_nonce = nonce
        user.challenge_timestamp = timestamp
        self.db.commit()
        return ChallengeResponse(nonce=nonce, timestamp=timestamp)

    def verify_challenge_response(self, username: str, nonce: str, timestamp: str, signature: str, certificate: str) -> bool:
        challenge_nonce = self.db.query(User.challenge_nonce).filter(User.username == username).scalar()
        challenge_timestamp = self.db.query(User.challenge_timestamp).filter(User.username == username).scalar()
        if not challenge_nonce or not challenge_timestamp:
            raise Exception("Aucun challenge généré pour cet utilisateur")
        if timestamp != challenge_timestamp:
            raise Exception("Timestamp invalide")
        else :
            if (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(challenge_timestamp.replace('Z', '+00:00'))).total_seconds() > 300:
                raise Exception("Le challenge a expiré")
        if nonce != challenge_nonce:
            raise Exception("Nonce invalide")

        verification_data = f"{nonce}:{timestamp}".encode()
        try:
            cert = x509.load_pem_x509_certificate(certificate.encode(), default_backend())
            public_key = cert.public_key()
            public_key.verify(
            bytes.fromhex(signature),
            verification_data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            self.clear_challenge(username)
            return True
        except Exception as e:
            raise Exception(f"Erreur lors de la vérification du challenge: {str(e)}")
    
    def clear_challenge(self, username: str):
        user = self.db.query(User).filter(User.username == username).first()
        if user:
            user.challenge_nonce = None
            user.challenge_timestamp = None
            self.db.commit()
        return True

    def _keycloak_admin(self) -> KeycloakAdmin:
        return KeycloakAdmin(
            server_url=os.getenv("KEYCLOAK_SERVER_URL"),
            username=os.getenv("KEYCLOAK_ADMIN"),
            password=os.getenv("KEYCLOAK_ADMIN_PASSWORD"),
            realm_name=os.getenv("KEYCLOAK_REALM"),
            user_realm_name="master",
            verify=resolve_keycloak_verify(),
        )

    # Les deux étapes que comporte un "reset complet" sur ce realm passwordless :
    # le 2FA (TOTP) et la clé d'accès WebAuthn. Le mot de passe n'existe pas dans
    # le flow `Password-less`, donc on l'exclut volontairement.
    _RESET_ACTIONS = ["CONFIGURE_TOTP", "webauthn-register-passwordless"]

    # Types de credentials Keycloak qu'on rotate sur un reset passwordless.
    # On ignore tout autre type (cookies SSO, etc.) pour ne pas casser le compte.
    _RESET_CREDENTIAL_TYPES = ("otp", "webauthn-passwordless")

    # Attribut Keycloak posé à la demande de reset, lu au callback OIDC pour
    # déterminer quels credentials sont "anciens".
    _RESET_CLEANUP_ATTR = "pending_credentials_cleanup"

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)

    def _set_cleanup_marker(self, admin: KeycloakAdmin, user_id: str) -> None:
        """Pose un timestamp ms sur l'attribut `pending_credentials_cleanup`.
        Lecture-modification-écriture pour ne pas écraser les autres attributs."""
        user = admin.get_user(user_id) or {}
        attrs = dict(user.get("attributes") or {})
        attrs[self._RESET_CLEANUP_ATTR] = [str(self._now_ms())]
        admin.update_user(user_id=user_id, payload={"attributes": attrs})

    def _clear_cleanup_marker(self, admin: KeycloakAdmin, user_id: str, attrs: dict) -> None:
        new_attrs = {k: v for k, v in attrs.items() if k != self._RESET_CLEANUP_ATTR}
        admin.update_user(user_id=user_id, payload={"attributes": new_attrs})

    def cleanup_old_credentials_after_reset(self, user_id: str) -> None:
        """À appeler dans le callback OIDC, après que la session est posée.

        Si le compte porte le marqueur `pending_credentials_cleanup`, supprime
        les credentials TOTP/WebAuthn créés *avant* ce marqueur (les nouveaux,
        enrôlés depuis, sont conservés), puis efface le marqueur.

        Idempotent : sans marqueur ou sans credentials anciens, no-op.
        N'élève jamais : un échec ne doit pas casser le login. Le marqueur
        n'est *pas* effacé en cas d'erreur, le prochain login retentera."""
        try:
            admin = self._keycloak_admin()
            user = admin.get_user(user_id) or {}
        except Exception:
            return
        attrs = user.get("attributes") or {}
        raw_marker = (attrs.get(self._RESET_CLEANUP_ATTR) or [None])[0]
        if not raw_marker:
            return
        try:
            marker_ms = int(raw_marker)
        except (TypeError, ValueError):
            # Marqueur corrompu : on l'enlève sans rien supprimer.
            try:
                self._clear_cleanup_marker(admin, user_id, attrs)
            except Exception:
                pass
            return

        try:
            credentials = admin.get_credentials(user_id) or []
        except Exception:
            return

        for cred in credentials:
            if cred.get("type") not in self._RESET_CREDENTIAL_TYPES:
                continue
            created = cred.get("createdDate") or 0
            cred_id = cred.get("id")
            if not cred_id or created >= marker_ms:
                continue
            try:
                admin.delete_credential(user_id, cred_id)
            except Exception:
                # On n'interrompt pas la boucle : on tente les autres credentials.
                continue

        try:
            self._clear_cleanup_marker(admin, user_id, attrs)
        except Exception:
            pass

    def send_credentials_reset_email(self, email: str) -> None:
        """Envoie un mail Keycloak pour ré-enrôler les credentials passwordless (TOTP + WebAuthn).

        Le realm est en browserFlow `Password-less` : la "réinitialisation des
        identifiants" = nouvel OTP + nouvelle passkey. Pas de mot de passe.

        On clear d'abord les `requiredActions` existantes sur le compte (sinon une
        ancienne `UPDATE_PASSWORD` héritée d'un précédent realm s'exécute en plus
        du token et redirige vers une page mot de passe inutile).

        Ne lève pas si l'email est inconnu : la route appelante répond toujours 200
        pour éviter l'énumération.

        On force `client_id` + `redirect_uri` car sans eux Keycloak génère un lien
        vers le client `account` (page blanche chez nous) et un redirect par défaut
        qui n'est pas dans nos `redirectUris`."""
        admin = self._keycloak_admin()
        users = admin.get_users({"email": email, "exact": True})
        if not users:
            return
        user_id = users[0].get("id")
        if not user_id:
            return

        # Remplacement explicite des requiredActions pour balayer toute ancienne
        # action (UPDATE_PASSWORD résiduelle, VERIFY_EMAIL...).
        admin.update_user(user_id=user_id, payload={"requiredActions": []})

        # Marqueur lu au callback OIDC : tout credential TOTP/WebAuthn antérieur
        # à cet instant sera supprimé après un login réussi avec les nouveaux.
        self._set_cleanup_marker(admin, user_id)

        client_id = os.getenv("KEYCLOAK_CLIENT_ID", "health_app_frontend")
        redirect_uri = os.getenv("FRONTEND_URL", "https://localhost").rstrip("/") + "/login"
        admin.send_update_account(
            user_id=user_id,
            payload=self._RESET_ACTIONS,
            client_id=client_id,
            redirect_uri=redirect_uri,
            lifespan=3600,
        )

    def force_credentials_reset(self, username: str) -> None:
        """Force le ré-enrôlement OTP + passkey à la prochaine connexion (médecin via certificat).
        Le mot de passe n'est pas dans la liste : ce realm n'en utilise pas pour ce flow."""
        admin = self._keycloak_admin()
        users = admin.get_users({"username": username, "exact": True})
        if not users:
            raise Exception("Utilisateur introuvable")
        user_id = users[0].get("id")
        admin.update_user(
            user_id=user_id,
            payload={"requiredActions": list(self._RESET_ACTIONS)},
        )
        # Voir send_credentials_reset_email : même mécanisme de nettoyage différé.
        self._set_cleanup_marker(admin, user_id)