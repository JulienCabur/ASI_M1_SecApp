import datetime
import os

class LogsService:
    """
    Classe de service pour la gestion des logs.
    """
    def __init__(self):
        """
        Initialise le service de logs.
        """
        self.logs = []
        self.service_path = "/var/log/service_logs.log"
        self.api_path = "/var/log/api_logs.log"
        self.category = ["INFO", "WARNING", "ERROR", "DEBUG"]

    def add_logs(self, logs: list[str], category=None, log_type="service"):
        """
        Méthode pour ajouter des logs au service.
        :param logs: Liste des messages de log à ajouter.
        :param category: Catégorie du log (INFO, WARNING, ERROR, DEBUG).
        :param log_type: Type de log (service, api, web).
        :return: True si les logs ont été ajoutés avec succès.
        """
        if log_type == "service" :
            log_file_path = self.service_path  
        else:
            log_file_path = self.api_path

        with open(log_file_path, "a+") as log_file:
            for log in logs:
                if not category:
                    category = "INFO"

                log_line = self.create_log_line(log, category)
                log_file.write(log_line + "\n")

        if log_type == "web":
            if not os.path.exists(self.weblog_path):
                try:
                    os.makedirs(os.path.dirname(self.weblog_path), exist_ok=True)
                    with open(self.weblog_path, "w+") as log_file:
                        log_file.write("")

                except Exception as e:
                    raise Exception(f"Failed to create log file: {e}")

            try:
                with open(self.weblog_path, "a+") as log_file:
                    for log in logs:
                        log_line = self.create_log_line(log, category)
                        log_file.writelines(log_line + "\n")

            except Exception as e:
                raise Exception(f"Failed to write web log: {e}")

        return True


    def get_logs(self, log_type="service"):
        """
        Méthode pour récupérer les logs.
        :param log_type: Type de log à récupérer (service, api, web, websocket).
        :return: Liste des logs récupérés.
        """
        if log_type == "service":
            log_file_path = self.service_path
        elif log_type == "api":
            log_file_path = self.api_path
        elif log_type == "web":
            log_file_path = self.weblog_path
        elif log_type == "websocket":
            log_file_path = self.websocket_path
        else:
            log_file_path = self.service_path

        try:
            with open(log_file_path, "r+") as log_file:
                self.logs = log_file.readlines()

        except FileNotFoundError:
            self.logs = []

        except Exception as e:
            raise Exception(f"Failed to read log file: {e}")

        return self.logs


    def get_logs_of_category(self, category):
        """
        Méthode pour récupérer les logs d'une catégorie spécifique.
        :param category: Catégorie de log à filtrer (INFO, WARNING, ERROR, DEBUG).
        :return: Liste des logs filtrés par catégorie.
        """
        if category not in self.category:
            raise ValueError(f"Invalid log category: {category}")

        service_logs = self.get_logs()
        api_logs = self.get_logs(log_type="api")
        web_logs = self.get_logs(log_type="web")
        websocket_logs = self.get_logs(log_type="websocket")
        all_logs = service_logs + api_logs + web_logs + websocket_logs
        filtered_logs = []

        for log in all_logs:
            if log.startswith(category):
                filtered_logs.append(log)
    
        return filtered_logs


    def create_log_line(self, message, category):
        """
        Crée une ligne de log formatée avec un timestamp.
        :param message: Message de log.
        :param category: Catégorie du log (INFO, WARNING, ERROR, DEBUG).
        :return: Ligne de log formatée.
        """
        if category not in self.category:
            raise ValueError(f"Invalid log category: {category}")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return f"{category}: [{timestamp}] - {message}"
    
    def get_logs_from_interval(self, start_time, end_time):
        """
        Méthode pour récupérer les logs dans un intervalle de temps spécifique.
        :param start_time: Heure de début au format "YYYY-MM-DD HH:MM:SS".
        :param end_time: Heure de fin au format "YYYY-MM-DD HH:MM:SS".
        :return: Liste des logs dans l'intervalle de temps spécifié.
        """
        start_time = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        end_time = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        service_logs = self.get_logs()
        api_logs = self.get_logs(log_type="api")
        web_logs = self.get_logs(log_type="web")
        websocket_logs = self.get_logs(log_type="websocket")
        all_logs = service_logs + api_logs + web_logs + websocket_logs
        filtered_logs = []

        for log in all_logs:
            log_timestamp = log.split("[")[1].split("]")[0]
            log_timestamp = datetime.datetime.strptime(log_timestamp, "%Y-%m-%d %H:%M:%S")
            if start_time <= log_timestamp <= end_time:
                filtered_logs.append(log)

        return filtered_logs


    def get_last_n_logs(self, n):
        """
        Méthode pour récupérer les n derniers logs.
        :param n: Nombre de logs à récupérer.
        :return: Liste des n derniers logs.
        """
        service_logs = self.get_logs()
        api_logs = self.get_logs(log_type="api")
        web_logs = self.get_logs(log_type="web")
        websocket_logs = self.get_logs(log_type="websocket")
        all_logs = service_logs + api_logs + web_logs + websocket_logs

        return all_logs[-n:]
    
    def get_logs_from_date(self, date):
        """
        Méthode pour récupérer les logs d'une date spécifique.
        :param date: Date au format "YYYY-MM-DD".
        :return: Liste des logs de la date spécifiée.
        """
        date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        service_logs = self.get_logs()
        api_logs = self.get_logs(log_type="api")
        web_logs = self.get_logs(log_type="web")
        websocket_logs = self.get_logs(log_type="websocket")
        all_logs = service_logs + api_logs + web_logs + websocket_logs
        filtered_logs = []

        for log in all_logs:
            log_timestamp = log.split("[")[1].split("]")[0]
            log_date = datetime.datetime.strptime(log_timestamp, "%Y-%m-%d %H:%M:%S").date()

            if log_date == date:
                filtered_logs.append(log)

        return filtered_logs
