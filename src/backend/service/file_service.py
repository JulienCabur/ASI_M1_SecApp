import base64
import os
from sqlalchemy.orm import Session
from schema.file_schema import FileBase
from models.file import File
import base64
import uuid

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

    def create_directory_service(self, username: str) -> str:
        """
        Crée un répertoire pour un utilisateur donné.
        :param username: Nom de l'utilisateur pour lequel créer le répertoire.
        :return: Chemin du répertoire créé.
        """
        user_directory = os.path.join(self.storage_path, username)
        if not os.path.exists(user_directory):
            os.makedirs(user_directory)
        return user_directory

    def get_base64_file_content(self, cert_path: str) -> bytes:
        with open(cert_path, "rb") as f:
            p12_content = base64.b64encode(f.read()).decode('utf-8')
        return p12_content
    
    def save_file(self, file, username: str) -> FileBase:
        """
        Enregistre un fichier pour un utilisateur donné.
        :param file: Fichier à enregistrer.
        :param username: Nom de l'utilisateur pour lequel enregistrer le fichier.
        :return: Chemin du fichier enregistré.
        """
        user_directory = self.create_directory_service(username)
        
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
            os.remove(file_path)
            self.db.delete(file_record)
            self.db.commit()
            return f"Fichier '{file}' supprimé avec succès pour l'utilisateur '{username}'."
        except Exception as e:
            return f"Erreur lors de la suppression du fichier: {str(e)}"
    
    def list_files(self, username: str) -> list:
        """
        Liste les fichiers d'un utilisateur donné. 
        :param username: Nom de l'utilisateur pour lequel lister les fichiers.
        :return: Liste des fichiers de l'utilisateur.
        """
        user_directory = self.create_directory_service(username)
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

    def edit_file(self, file: str, new_content: bytes, username: str) -> str:
        """
        Modifie le contenu d'un fichier pour un utilisateur donné.
        :param file: Fichier à modifier.
        :param new_content: Nouveau contenu du fichier.
        :param username: Nom de l'utilisateur pour lequel modifier le fichier.
        :return: Message de confirmation de la modification du fichier.
        """
        user_directory = self.create_directory_service(username)
        file_path = os.path.join(user_directory, file)
        
        if not os.path.exists(file_path):
            return f"Le fichier '{file}' n'existe pas dans le répertoire de l'utilisateur '{username}'."
        
        try:
            with open(file_path, 'wb') as f:
                f.write(new_content)
            return f"Fichier '{file}' modifié avec succès pour l'utilisateur '{username}'."
        except Exception as e:
            return f"Erreur lors de la modification du fichier: {str(e)}"
