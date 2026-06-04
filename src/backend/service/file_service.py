import base64
import os
import uuid

from sqlalchemy.orm import Session

from models.file import File
from models.file_requests import FileOperationRequest
from models.relation import Relation
from schema.file_requests_schema import OperationType, RequestStatus
from schema.file_schema import FileBase


def _secure_delete(path: str) -> None:
    """Écrase le fichier avec des octets aléatoires avant de le supprimer.

    Empêche la récupération du contenu par analyse des blocs libérés sur le
    système de fichiers (attaque par rémanence). Un seul passage suffit pour
    les disques modernes (magnétiques ou SSD).
    """
    try:
        size = os.path.getsize(path)
        with open(path, "r+b") as f:
            f.write(os.urandom(size))
            f.flush()
            os.fsync(f.fileno())
        os.remove(path)
    except FileNotFoundError:
        pass
    except Exception:
        # Fallback : suppression simple si l'écrasement échoue (fichier en lecture seule, etc.)
        try:
            os.remove(path)
        except Exception:
            pass

class FileService:
    """
    Classe pour gérer les opérations liées aux fichiers.
    """
    def __init__(self, db: Session, storage_path: str):
        """
        Initialise le service de gestion des fichiers avec une session de base de données et un chemin de stockage.
        :param db: Session de base de données SQLAlchemy.
        :param storage_path: Chemin du répertoire de stockage des fichiers.
        """
        self.db = db
        self.storage_path = storage_path
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path)
        self.temp_storage_path = "/temp_storage"
        if not os.path.exists(self.temp_storage_path):
            os.makedirs(self.temp_storage_path)

    def create_directory_service(self, username: str, temporary: bool = False) -> str:
        """
        Crée un répertoire pour un utilisateur donné.
        :param username: Nom de l'utilisateur pour lequel créer le répertoire.
        :param temporary: Indique si le répertoire est temporaire.
        :return: Chemin du répertoire créé.
        """
        if temporary:
            user_directory = os.path.join(self.temp_storage_path, username)
        else:
            user_directory = os.path.join(self.storage_path, username)
        if not os.path.exists(user_directory):
            os.makedirs(user_directory)
        return user_directory

    def get_base64_file_content(self, cert_path: str) -> bytes:
        with open(cert_path, "rb") as f:
            p12_content = base64.b64encode(f.read()).decode('utf-8')
        return p12_content
    
    def save_file(self, file, username: str, doctor_id: str = None) -> FileBase:
        """
        Enregistre un fichier pour un utilisateur donné.
        :param file: Fichier à enregistrer.
        :param username: Nom de l'utilisateur pour lequel enregistrer le fichier.
        :param doctor_id: ID du médecin pour lequel enregistrer le fichier.
        :return: Chemin du fichier enregistré.
        """
        user_directory = self.create_directory_service(username)
        if doctor_id:
            relation = self.db.query(Relation).filter(Relation.patient_id == username, Relation.doctor_id == doctor_id).first()
            if not relation or not relation.is_verified:
                raise Exception("Relation non vérifiée entre le médecin et le patient.")
        if file not in os.listdir(user_directory):
            raise FileNotFoundError(f"Le fichier '{file}' n'existe pas dans le répertoire de l'utilisateur '{username}'.")
        file_record = self.db.query(File).filter(File.name == file, File.user_id == username).first()
        if not file_record:
            raise Exception(f"Aucun enregistrement de fichier trouvé pour '{file}' et l'utilisateur '{username}'.")
        file_path = os.path.join(user_directory, file)

        return FileBase(path=file_path, name=file, ciphered_dek=file_record.ciphered_dek)
    
    def upload_file(self, file, username: str, dek: str, date: str) -> str:
        """
        Gère le processus de téléversement d'un fichier pour un utilisateur donné.
        :param file: Fichier à téléverser. `file.filename` est attendu sous forme
                     de nom chiffré (b64url) — le serveur ne l'interprète jamais en clair.
        :param username: Nom de l'utilisateur pour lequel téléverser le fichier.
        :param dek: Enveloppe (JSON-base64) contenant le DEK wrappé et les IVs.
        :param date: Date d'upload chiffrée côté client (b64), opaque pour le serveur.
        :return: Chemin du fichier téléchargé.
        """
        try:
            contents = file.file.read()
            file_record = File(uuid=uuid.uuid4(), name=file.filename, date=date, user_id=username, ciphered_dek=dek)
            self.db.add(file_record)
            self.db.commit()
            with open(os.path.join(self.storage_path, username, file.filename), 'wb') as f:
                f.write(contents)

        except Exception as e:
            return f"Erreur lors du téléchargement du fichier: {str(e)}"
        finally:
            file.file.close()

        return f"Fichier '{file.filename}' téléchargé avec succès pour l'utilisateur '{username}'."

    def upload_file_for_doctor(self, file, patient_id: str, doctor_id: str, dek: str, date: str) -> str:
        """
        Gère le processus de téléversement d'un fichier pour un patient par un médecin.
        :param file: Fichier à téléverser. `file.filename` est attendu sous forme
                     de nom chiffré (b64url) — le serveur ne l'interprète jamais en clair.
        :param patient_id: ID du patient pour lequel téléverser le fichier.
        :param doctor_id: ID du médecin qui téléverse le fichier.
        :param dek: Enveloppe (JSON-base64) contenant le DEK wrappé et les IVs.
        :param date: Date d'upload chiffrée côté client (b64), opaque pour le serveur.
        :return: Chemin du fichier téléchargé.
        """
        try:
            relation = self.db.query(Relation).filter(Relation.patient_id == patient_id, Relation.doctor_id == doctor_id).first()
            if not relation or not relation.is_verified:
                raise Exception("Relation non vérifiée entre le médecin et le patient.")
            self.create_directory_service(patient_id, temporary=True)
            file_request = FileOperationRequest(
                id=uuid.uuid4(),
                relation_id=relation.id,
                operation_type=OperationType.CREATE,
                status=RequestStatus.PENDING,
                file_name=file.filename,
                date=date,
                ciphered_dek=dek
            )
            self.db.add(file_request)
            self.db.commit()

            contents = file.file.read()
            with open(os.path.join(self.temp_storage_path, patient_id, file.filename), 'wb') as f:
                f.write(contents)

        except Exception as e:            
            return f"Erreur de relation: {str(e)}"
    
    def delete_file_for_doctor(self, file_name: str, patient_id: str, doctor_id: str) -> str:
        """
        Gère le processus de suppression d'un fichier pour un patient par un médecin.
        :param file_name: Nom du fichier à supprimer.
        :param patient_id: ID du patient pour lequel supprimer le fichier.
        :param doctor_id: ID du médecin qui supprime le fichier.
        :return: Message de confirmation de la suppression du fichier.
        """
        try:
            relation = self.db.query(Relation).filter(Relation.patient_id == patient_id, Relation.doctor_id == doctor_id).first()
            if not relation or not relation.is_verified:
                raise Exception("Relation non vérifiée entre le médecin et le patient.")
            file_record = self.db.query(File).filter(File.name == file_name, File.user_id == patient_id).first()
            if not file_record:
                raise Exception(f"Aucun enregistrement de fichier trouvé pour '{file_name}' et le patient '{patient_id}'.")
            file_request = FileOperationRequest(
                id=uuid.uuid4(),
                relation_id=relation.id,
                operation_type=OperationType.DELETE,
                status=RequestStatus.PENDING,
                file_name=file_name,
                date=file_record.date,
                ciphered_dek=file_record.ciphered_dek
            )
            self.db.add(file_request)
            self.db.commit()

        except Exception as e:            
            return f"Erreur de relation: {str(e)}"
    
    def delete_file(self, file: str, username: str) -> str:
        """
        Supprime un fichier pour un utilisateur donné.
        :param file: Fichier à supprimer.
        :param username: Nom de l'utilisateur pour lequel supprimer le fichier.
        :return: Message de confirmation de la suppression du fichier.
        """
        user_directory = self.create_directory_service(username)
        file_path = os.path.join(user_directory, file)
        if not os.path.exists(file_path):
            return f"Le fichier '{file}' n'existe pas dans le répertoire de l'utilisateur '{username}'."
        
        try:
            file_record = self.db.query(File).filter(File.name == file).first()
            if not file_record:
                return f"Aucun enregistrement de fichier trouvé pour '{file}'."
            if file_record.user_id != username:
                return f"Le fichier '{file}' n'appartient pas à l'utilisateur '{username}'."
            _secure_delete(file_path)
            self.db.delete(file_record)
            self.db.commit()
            return f"Fichier '{file}' supprimé avec succès pour l'utilisateur '{username}'."
        except Exception as e:
            return f"Erreur lors de la suppression du fichier: {str(e)}"
    
    def list_files(self, username: str, doctor_id: str = None) -> list:
        """
        Liste les fichiers d'un utilisateur donné. 
        :param username: Nom de l'utilisateur pour lequel lister les fichiers.
        :param doctor_id: ID du médecin pour lequel lister les fichiers.
        :return: Liste des fichiers de l'utilisateur.
        """
        user_directory = self.create_directory_service(username)
        if doctor_id:
            relation = self.db.query(Relation).filter(Relation.patient_id == username, Relation.doctor_id == doctor_id).first()
            if not relation or not relation.is_verified:
                raise Exception("Relation non vérifiée entre le médecin et le patient.")
        files_list = []
        for file in os.listdir(user_directory):
            file_record = self.db.query(File).filter(File.name == file, File.user_id == username).first()
            if file_record:
                files_list.append({
                    "name": file,
                    "date": file_record.date,
                    "ciphered_dek": file_record.ciphered_dek
                })
        return files_list

    def delete_user_storage(self, user_id: str) -> None:
        """Supprime de façon sécurisée tous les fichiers d'un utilisateur.
        """
        for base in (self.storage_path, self.temp_storage_path):
            user_dir = os.path.join(base, user_id)
            if not os.path.isdir(user_dir):
                continue
            for fname in os.listdir(user_dir):
                _secure_delete(os.path.join(user_dir, fname))
            try:
                os.rmdir(user_dir)
            except Exception:
                pass
