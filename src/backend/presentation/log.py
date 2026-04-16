from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from service.log_service import LogsService
from core.database import get_db
import requests
from presentation.auth import get_current_user

router = APIRouter( # Crée un routeur APIRouter pour les routes liées aux logs
    prefix="/logs",
    tags=["logs"],
)


@router.get("/all", dependencies=[Depends(get_current_user)])
def get_service_logs():
    """
    Récupère tous les logs du service.
    :return: Liste de tous les logs.
    """
    try:
        log_service = LogsService()
        log_service.add_logs(["Received request to retrieve service logs"], category="INFO", log_type="api")
        service_logs = log_service.get_logs()
        api_logs = log_service.get_logs(log_type="api")
        logs = service_logs + api_logs
        if not logs:
            log_service.add_logs(["No logs found in the service."], category="INFO", log_type="api")
            raise HTTPException(status_code=404, detail="Logs not found")

        log_service.add_logs([f"Retrieved {len(logs)} logs from the service."], category="INFO", log_type="api")
        return logs

    except Exception as e:
        log_service.add_logs([f"Error occurred while retrieving logs: {e}"], category="ERROR", log_type="api")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/type", dependencies=[Depends(get_current_user)])
def get_type_logs(log_type: str = Query(..., description="Type de logs à récupérer (service, api, web, websocket)", example="service")):
    """
    Récupère les logs d'un type spécifique (service, api, web, websocket).
    :param log_type: Type de logs à récupérer (service, api, web, websocket).
    :return: Liste des logs du type spécifié.
    """
    try:
        log_service = LogsService()
        log_service.add_logs([f"Received request to retrieve logs of type: {log_type}"], category="INFO", log_type="api")
        logs = log_service.get_logs(log_type=log_type)

        if not logs:
            log_service.add_logs([f"No logs found in the {log_type} logs."], category="INFO", log_type="api")
            raise HTTPException(status_code=404, detail="Logs not found")

        log_service.add_logs([f"Retrieved {len(logs)} logs from the {log_type} logs."], category="INFO", log_type="api")
        return logs

    except Exception as e:
        log_service.add_logs([f"Error occurred while retrieving API logs: {e}"], category="ERROR", log_type="api")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/category", dependencies=[Depends(get_current_user)])
def get_logs_by_category(category: str = Query(..., description="Catégorie des logs à récupérer (ERROR, INFO, DEBUG, WARNING)", example="ERROR")):
    """
    Récupère les logs d'une catégorie spécifique (ERROR, INFO, DEBUG, WARNING).
    :param category: Catégorie des logs à récupérer.
    :return: Liste des logs de la catégorie spécifiée.
    """
    try:
        log_service = LogsService()
        log_service.add_logs([f"Received request to retrieve logs for category: {category}"], category="INFO", log_type="api")
        all_logs = log_service.get_logs_of_category(category)

        if not all_logs:
            log_service.add_logs([f"No logs found for category: {category}"], category="INFO", log_type="api")
            raise HTTPException(status_code=404, detail="No logs found for the specified category")

        log_service.add_logs([f"Retrieved {len(all_logs)} logs for category: {category}"], category="INFO", log_type="api")
        return all_logs

    except ValueError as ve:
        log_service.add_logs([f"Category is not in the list: {ve}"], category="ERROR", log_type="api")
        raise HTTPException(status_code=400, detail=str(ve))

    except Exception as e:
        log_service.add_logs([f"Error occurred while retrieving logs: {e}"], category="ERROR", log_type="api")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/interval", dependencies=[Depends(get_current_user)])
def get_logs_by_interval(
    start_time: str = Query(
        ...,
        description="Heure de début au format YYYY-MM-DD HH:MM (ex: 2025-11-02 14:30:00)",
        example="2025-11-02 14:30:00"),
    end_time: str = Query(
        ...,
        description="Heure de fin au format YYYY-MM-DD HH:MM (ex: 2025-11-02 15:30:00)",
        example="2025-11-02 15:30:00")
    ):
    """
    Récupère les logs dans un intervalle de temps spécifique.
    :param start_time: Heure de début au format YYYY-MM-DD HH:MM.
    :param end_time: Heure de fin au format YYYY-MM-DD HH:MM.
    :return: Liste des logs dans l'intervalle de temps spécifié.
    """
    try:
        log_service = LogsService()
        log_service.add_logs([f"Received request to retrieve logs from {start_time} to {end_time}"], category="INFO", log_type="api")
        interval_logs = log_service.get_logs_from_interval(start_time, end_time)

        if not interval_logs:
            log_service.add_logs([f"No logs found in the specified time interval"], category="INFO", log_type="api")
            raise HTTPException(status_code=404, detail="No logs found in the specified time interval")
        
        log_service.add_logs([f"Retrieved {len(interval_logs)} logs from the specified time interval"], category="INFO", log_type="api")
        return interval_logs

    except Exception as e:
        log_service.add_logs([f"Error occurred while retrieving logs: {e}"], category="ERROR", log_type="api")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/date", dependencies=[Depends(get_current_user)])
def get_logs_by_date(date: str = Query(..., description="Date au format YYYY-MM-DD (ex: 2025-11-02)", example="2025-11-02")):
    """
    Récupère les logs d'une date spécifique.
    :param date: Date au format YYYY-MM-DD.
    :return: Liste des logs de la date spécifiée.
    """
    try:
        log_service = LogsService()
        log_service.add_logs([f"Received request to retrieve logs for date: {date}"], category="INFO", log_type="api")
        date_logs = log_service.get_logs_from_date(date)

        if not date_logs:
            log_service.add_logs([f"No logs found for date: {date}"], category="INFO", log_type="api")
            raise HTTPException(status_code=404, detail="No logs found for the specified date")

        log_service.add_logs([f"Retrieved {len(date_logs)} logs for date: {date}"], category="INFO", log_type="api")
        return date_logs

    except Exception as e:
        log_service.add_logs([f"Error occurred while retrieving logs: {e}"], category="ERROR", log_type="api")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/last", dependencies=[Depends(get_current_user)])
def get_last_n_logs(n: int):
    """
    Récupère les derniers n logs.
    :param n: Nombre de logs à récupérer.
    :return: Liste des derniers n logs.
    """
    try:
        log_service = LogsService()
        log_service.add_logs([f"Received request to retrieve last {n} logs"], category="INFO", log_type="api")
        last_logs = log_service.get_last_n_logs(n)

        if not last_logs:
            log_service.add_logs([f"No logs found when retrieving last {n} logs"], category="INFO", log_type="api")
            raise HTTPException(status_code=404, detail="No logs found")

        log_service.add_logs([f"Retrieved {len(last_logs)} logs"], category="INFO", log_type="api")
        return last_logs

    except Exception as e:
        log_service.add_logs([f"Error occurred while retrieving logs: {e}"], category="ERROR", log_type="api")
        raise HTTPException(status_code=500, detail="Internal Server Error")