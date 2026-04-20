import os
from sqlalchemy.orm import Session

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
    
    def save_file(self, file, username: str) -> str:
        """
        Enregistre un fichier pour un utilisateur donné.
        :param file: Fichier à enregistrer.
        :param username: Nom de l'utilisateur pour lequel enregistrer le fichier.
        :return: Chemin du fichier enregistré.
        """
        user_directory = self.create_directory_service(username)
        
        if file not in os.listdir(user_directory):
            raise FileNotFoundError(f"Le fichier '{file}' n'existe pas dans le répertoire de l'utilisateur '{username}'.")
        
        file_path = os.path.join(user_directory, file)

        return file_path
    
    def upload_file(self, file, username: str) -> str:
        """
        Gère le processus de téléversement d'un fichier pour un utilisateur donné.
        :param file: Fichier à téléverser.
        :param username: Nom de l'utilisateur pour lequel téléverser le fichier.
        :return: Chemin du fichier téléchargé.
        """
        try:
            contents = file.file.read()
            with open(os.path.join(self.storage_path, username, file.filename), 'wb') as f:
                f.write(contents)
        except Exception as e:
            return f"Erreur lors du téléchargement du fichier: {str(e)}"
        finally:
            file.file.close()

        return f"Fichier '{file.filename}' téléchargé avec succès pour l'utilisateur '{username}'."
