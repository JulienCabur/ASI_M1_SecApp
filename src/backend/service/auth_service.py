
import datetime
import secrets
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from schema.auth_schema import UserInDB, CertificateRequest, ChallengeResponse
from models.user import User
from keycloak import KeycloakAdmin
from keycloak.exceptions import KeycloakPostError
from dotenv import load_dotenv
from core.auth import resolve_keycloak_verify
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509.oid import NameOID
import os


load_dotenv()  # Charger les variables d'environnement depuis le fichier .env

def _env(name: str, default=None, required: bool = False):
    """Lire une variable d'environnement avec un comportement centralisé.

    - `default` retourné si la variable est absente
    - si `required=True` et la valeur est vide/None -> RuntimeError
    """
    val = os.getenv(name, default)
    if required and (val is None or val == ""):
        raise RuntimeError(f"Environment variable {name} is required but not set")
    return val


class DoctorConflictError(Exception):
    """Conflit d'unicité côté Keycloak lors de l'enregistrement d'un médecin.

    `field` vaut "username" ou "email" et permet à la couche présentation de
    renvoyer un message ciblé sans réinterpréter la chaîne d'erreur Keycloak.
    """

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field


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
        self.ca_chain_path = "/app/certs/ca-chain.pem"

    def store_user(self, user_data: UserInDB) -> User:
        """
        Stocke un nouvel utilisateur dans la base de données.
        :param user_data: Données de l'utilisateur à stocker.
        :return: L'utilisateur stocké.
        """
        if self.db.query(User).filter(User.id == user_data.id).first():
            raise Exception("Utilisateur déjà existant")
        user = User(id=user_data.id, username=user_data.username, roles="patient")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    # Politique CSR : 2048 bits min (aligné sur le default_bits de la PKI),
    # 4096 max pour éviter des CSR pathologiquement gros.
    _CSR_KEY_MIN_BITS = 2048
    _CSR_KEY_MAX_BITS = 4096
    # Borne max sur la taille du CSR envoyé pour éviter qu'un POST géant
    # remplisse le volume partagé avec la PKI avant validation.
    _CSR_MAX_BYTES = 16 * 1024

    def submit_browser_csr(self, csr_pem: str, common_name: str, organization: str) -> str:
        """Valide un CSR généré par le navigateur puis le dépose pour la PKI.

        Le subject DOIT correspondre exactement à ce que la PKI accepte (policy
        `match_pol` dans signing-ca.conf : DC=be, DC=healthapp, O=<organization>,
        CN=<username>). Sans cette vérification, un navigateur malveillant
        pourrait soumettre un CSR avec un CN différent du username demandé et
        obtenir un certificat signé pour un autre médecin.
        """
        if not csr_pem or len(csr_pem.encode("utf-8")) > self._CSR_MAX_BYTES:
            raise Exception("CSR vide ou trop volumineux")

        try:
            csr = x509.load_pem_x509_csr(csr_pem.encode("utf-8"), default_backend())
        except Exception as e:
            raise Exception(f"CSR illisible: {str(e)}")

        # Prouve que le navigateur détient la clé privée correspondante.
        if not csr.is_signature_valid:
            raise Exception("Signature du CSR invalide (preuve de possession KO)")

        public_key = csr.public_key()
        if not isinstance(public_key, rsa.RSAPublicKey):
            raise Exception("Seules les clés RSA sont acceptées")
        if not (self._CSR_KEY_MIN_BITS <= public_key.key_size <= self._CSR_KEY_MAX_BITS):
            raise Exception(
                f"Taille de clé RSA invalide ({public_key.key_size} bits)"
            )

        # Lecture du subject : on impose exactement DC=be, DC=healthapp,
        # O=<organization>, CN=<username>. L'ordre n'a pas d'importance ici,
        # OpenSSL le réordonnera selon le policy au moment de la signature.
        attrs = {oid: [v.value for v in csr.subject.get_attributes_for_oid(oid)] for oid in {
            NameOID.DOMAIN_COMPONENT,
            NameOID.ORGANIZATION_NAME,
            NameOID.COMMON_NAME,
        }}

        dcs = [d.lower() for d in attrs.get(NameOID.DOMAIN_COMPONENT, [])]
        if sorted(dcs) != ["be", "healthapp"]:
            raise Exception("Domain components attendus: DC=be, DC=healthapp")

        o_vals = attrs.get(NameOID.ORGANIZATION_NAME, [])
        if len(o_vals) != 1 or o_vals[0] != organization:
            raise Exception("L'organisation du CSR ne correspond pas à celle demandée")

        cn_vals = attrs.get(NameOID.COMMON_NAME, [])
        if len(cn_vals) != 1 or cn_vals[0] != common_name:
            raise Exception("Le CN du CSR doit correspondre au username demandé")

        # Refus précoce des SAN/extensions injectées : la conf PKI a
        # `copy_extensions = copy`, donc des extensions surprises (autres
        # CN dans un subjectAltName, p.ex.) seraient copiées dans le cert
        # signé. On ne tolère aucune extension dans le CSR.
        if list(csr.extensions):
            raise Exception("Les extensions ne sont pas autorisées dans le CSR")

        # Écriture atomique : .csr.tmp puis rename, sinon le watcher PKI
        # peut tomber sur un fichier partiellement écrit.
        csr_path = os.path.join(self.csr_repository, common_name + ".csr")
        tmp_path = csr_path + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(csr.public_bytes(serialization.Encoding.PEM))
        os.replace(tmp_path, csr_path)

        return csr_path

    def check_csr_signed(self, common_name: str) -> str:
        """Retourne le chemin du certificat signé par la PKI (PEM)."""
        path = self.cert_repository + "/" + common_name + ".crt"
        if not os.path.exists(path):
            raise Exception("Certificat non trouvé")
        return path

    def read_ca_chain_pem(self) -> str:
        """Lit la chaîne CA à embarquer dans le .p12 côté navigateur."""
        with open(self.ca_chain_path, "r", encoding="utf-8") as f:
            return f.read()
    
    def store_public_mek(self, doctor_id: str, public_mek: Dict[str, Any]) -> None:
        """Stocke la JWK publique MEK d'un médecin (colonne JSONB).

        `public_mek` est le dict issu de la JWK validée (clé publique RSA-OAEP).
        """
        user = self.db.query(User).filter(User.id == doctor_id).first()
        if not user:
            raise Exception("Utilisateur non trouvé")
        if user.roles != "doctor":
            raise Exception("L'utilisateur n'est pas un médecin")
        user.public_mek = public_mek
        self.db.commit()

    def _keycloak_admin(self) -> KeycloakAdmin:
        return KeycloakAdmin(
            server_url=_env("KEYCLOAK_SERVER_URL"),
            username=_env("KEYCLOAK_ADMIN"),
            password=_env("KEYCLOAK_ADMIN_PASSWORD"),
            realm_name=_env("KEYCLOAK_REALM"),
            user_realm_name="master",
            verify=resolve_keycloak_verify(),
        )

    def check_doctor_uniqueness(self, username: str, email: str) -> None:
        """Vérifie auprès de Keycloak qu'aucun compte ne porte déjà ce username
        ou cet email. Lève `DoctorConflictError` si un conflit est détecté.

        Cette pré-vérification évite d'émettre un certificat PKI qui devrait
        être révoqué juste après si la création Keycloak échoue."""
        admin = self._keycloak_admin()

        # `search=` matche aussi les sous-chaînes ; on filtre sur l'égalité exacte.
        username_norm = (username or "").strip().lower()
        email_norm = (email or "").strip().lower()

        if username_norm:
            for u in admin.get_users(query={"username": username_norm, "exact": True}):
                if (u.get("username") or "").lower() == username_norm:
                    raise DoctorConflictError("username", "Ce nom d'utilisateur est déjà utilisé.")

        if email_norm:
            for u in admin.get_users(query={"email": email_norm, "exact": True}):
                if (u.get("email") or "").lower() == email_norm:
                    raise DoctorConflictError("email", "Cette adresse e-mail est déjà utilisée.")

    @staticmethod
    def _conflict_field_from_keycloak(err: KeycloakPostError) -> str | None:
        raw = getattr(err, "error_message", None) or getattr(err, "response_body", b"")
        if isinstance(raw, (bytes, bytearray)):
            try:
                raw = raw.decode("utf-8", errors="replace")
            except Exception:
                raw = str(raw)
        text = (raw or "").lower()
        if "same username" in text or "username" in text:
            return "username"
        if "same email" in text or "email" in text:
            return "email"
        return None

    def create_doctor_in_keycloak(self, cert_path: str, user_info: CertificateRequest) -> str:
        """Crée le compte Keycloak associé au certificat fraîchement signé.

        Le retour est le PEM du certificat — le navigateur en a besoin pour
        assembler le .p12 (la clé privée n'a jamais quitté le navigateur, donc
        c'est lui qui construit le PKCS#12 final). Le serial du cert est stocké
        en attribut Keycloak pour pouvoir lier login OIDC ↔ cert plus tard.
        """
        with open(cert_path, "rb") as f:
            cert_pem_bytes = f.read()

        cert = x509.load_pem_x509_certificate(cert_pem_bytes, default_backend())
        serial_hex = f"{cert.serial_number:02X}"

        print(f"Création de l'utilisateur dans Keycloak avec le certificat: {cert_path}, numéro de série: {serial_hex}")

        keycloak_admin = self._keycloak_admin()

        user_payload = {
            "email": user_info.email,
            "username": user_info.username,
            "enabled": True,
            "firstName": user_info.first_name,
            "lastName": user_info.last_name,
            "groups": ["/Docteurs"],
            "attributes": {
                "certificate_serial": serial_hex,
                "date_of_birth": user_info.date_of_birth,
                "user_type": "doctor"
            }
        }

        try:
            new_user_id = keycloak_admin.create_user(user_payload, exist_ok=False)
            group_patient = keycloak_admin.get_group_by_path("/Patients")
            keycloak_admin.group_user_remove(new_user_id, group_patient['id'])
            user = User(
                id=new_user_id,
                username=user_info.username,
                roles="doctor",
                challenge_nonce=None
            )
            self.db.add(user)
            self.db.commit()

            return cert_pem_bytes.decode("utf-8")
        except KeycloakPostError as e:
            self.delete_sensitive_files(user_info.username)
            if getattr(e, "response_code", None) == 409:
                field = self._conflict_field_from_keycloak(e)
                if field == "username":
                    raise DoctorConflictError("username", "Ce nom d'utilisateur est déjà utilisé.")
                if field == "email":
                    raise DoctorConflictError("email", "Cette adresse e-mail est déjà utilisée.")
            raise Exception(f"Erreur lors de la création de l'utilisateur dans Keycloak: {str(e)}")
        except DoctorConflictError:
            self.delete_sensitive_files(user_info.username)
            raise
        except Exception as e:
            self.delete_sensitive_files(user_info.username)
            raise Exception(f"Erreur lors de la création de l'utilisateur dans Keycloak: {str(e)}")

    def delete_sensitive_files(self, common_name: str):
        """Nettoie les artefacts laissés côté serveur après émission du cert.

        Avec la nouvelle architecture, la clé privée ne touche jamais le
        serveur (générée par le navigateur). Il ne reste donc à supprimer
        que le CSR (au cas où le watcher PKI ne l'aurait pas encore consommé)
        et le .crt signé une fois lu et renvoyé au navigateur.
        """
        csr_path = os.path.join(self.csr_repository, common_name + ".csr")
        csr_tmp_path = os.path.join(self.csr_repository, common_name + ".csr.tmp")
        crt_path = os.path.join(self.cert_repository, common_name + ".crt")
        crt_tmp_path = os.path.join(self.cert_repository, common_name + ".crt.tmp")

        for path in [csr_path, csr_tmp_path, crt_path, crt_tmp_path]:
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

        try:
            cert = x509.load_pem_x509_certificate(certificate.encode(), default_backend())
        except Exception as e:
            raise Exception(f"Certificat illisible: {str(e)}")

        # Lie le certificat à l'username revendiqué : sans cette vérif, un porteur
        # de cert valide pourrait signer son propre challenge tout en revendiquant
        # le username d'un autre médecin, et la signature passerait avec la clé
        # publique du cert fourni.
        cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        cert_cn = cn_attrs[0].value if cn_attrs else None
        if not cert_cn or cert_cn != username:
            raise Exception("Le certificat ne correspond pas à l'utilisateur revendiqué")

        verification_data = f"{nonce}:{timestamp}".encode()
        try:
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

    # Les deux étapes que comporte un "reset complet" sur ce realm passwordless :
    # le 2FA (TOTP) et la clé d'accès WebAuthn. Le mot de passe n'existe pas dans
    # le flow `Password-less`, donc on l'exclut volontairement.
    _RESET_ACTIONS = ["webauthn-register-passwordless"]

    # Types de credentials Keycloak considérés comme "reset-ables".
    _RESET_CREDENTIAL_TYPES = ("webauthn-passwordless")

    _ACTION_TOKEN_LIFESPAN_SECONDS = 3600

    def _send_reenrollment_email(self, admin: KeycloakAdmin, user_id: str) -> None:
        """Envoie un mail Keycloak avec un action token qui force CONFIGURE_TOTP
        + webauthn-register-passwordless. Le token authentifie l'utilisateur
        sans qu'il ait à présenter ses credentials existants, et les required
        actions ajoutent de *nouveaux* credentials sans toucher aux anciens.

        On force `client_id` + `redirect_uri` car sans eux Keycloak génère un
        lien vers le client `account` (page blanche chez nous) et un redirect
        par défaut hors de nos `redirectUris`."""
        client_id = _env("KEYCLOAK_CLIENT_ID", "health_app_frontend")
        redirect_uri = _env("FRONTEND_URL", "https://localhost").rstrip("/") + "/login"
        admin.send_update_account(
            user_id=user_id,
            payload=list(self._RESET_ACTIONS),
            client_id=client_id,
            redirect_uri=redirect_uri,
            lifespan=self._ACTION_TOKEN_LIFESPAN_SECONDS,
        )

    def cleanup_stale_credentials(self, user_id: str) -> None:
        """Pour chaque type "reset-able" (TOTP, passkey passwordless), si le
        user en a plus d'un, on garde le plus récent (le credential fraîchement
        enrôlé) et on supprime les autres.

        Hook appelé après chaque callback OIDC : c'est ainsi qu'on supprime
        l'ancien TOTP/passkey *après* la création du nouveau dans le flow
        de reset. En régime nominal (un seul credential de chaque type), c'est
        un no-op. Aucun signal explicite de "reset en cours" n'est nécessaire :
        la pluralité des credentials suffit."""
        admin = self._keycloak_admin()
        try:
            credentials = admin.get_credentials(user_id) or []
        except Exception:
            return

        by_type: Dict[str, List[Dict[str, Any]]] = {t: [] for t in self._RESET_CREDENTIAL_TYPES}
        for cred in credentials:
            cred_type = cred.get("type")
            if cred_type in by_type and cred.get("id"):
                by_type[cred_type].append(cred)

        for creds in by_type.values():
            if len(creds) <= 1:
                continue
            # `createdDate` est en epoch millis. Le plus grand = le plus récent
            # = celui que l'utilisateur vient d'enrôler. On garde celui-là et
            # on supprime tout le reste (anciens credentials du flow de reset).
            creds.sort(key=lambda c: c.get("createdDate") or 0, reverse=True)
            for stale in creds[1:]:
                try:
                    admin.delete_credential(user_id, stale["id"])
                except Exception:
                    # Un id déjà supprimé ou introuvable ne doit pas bloquer
                    # le nettoyage des autres.
                    pass

    def send_credentials_reset_email(self, email: str) -> None:
        """Reset différé pour patient : on n'efface rien immédiatement, on
        envoie juste le mail d'action. Les required actions Keycloak font
        enrôler de nouveaux credentials *à côté* des anciens. La suppression
        des anciens a lieu au prochain callback OIDC, via
        `cleanup_stale_credentials` — c'est-à-dire seulement une fois que les
        nouveaux sont en place. Si le mail est perdu, l'utilisateur garde son
        accès.

        Ne lève pas si l'email est inconnu : la route appelante répond toujours
        200 pour éviter l'énumération."""
        admin = self._keycloak_admin()
        users = admin.get_users({"email": email, "exact": True})
        if not users:
            return
        user_id = users[0].get("id")
        if not user_id:
            return
        self._send_reenrollment_email(admin, user_id)

    def force_credentials_reset(self, username: str) -> None:
        """Reset différé pour médecin (via certificat) : on envoie le mail
        d'action sans toucher aux credentials existants. Cleanup des anciens
        au prochain callback OIDC une fois les nouveaux enrôlés."""
        admin = self._keycloak_admin()
        users = admin.get_users({"username": username, "exact": True})
        if not users:
            raise Exception("Utilisateur introuvable")
        user_id = users[0].get("id")
        if not user_id:
            raise Exception("Utilisateur introuvable")
        self._send_reenrollment_email(admin, user_id)