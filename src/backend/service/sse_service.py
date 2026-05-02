import asyncio
import json
from typing import Dict, List, Optional


class SSEManager:
    """
    Gestionnaire de connexions Server-Sent Events.
    Chaque user authentifié peut avoir plusieurs connexions ouvertes simultanément
    (plusieurs onglets). Les événements sont broadcastés à toutes les connexions
    de l'utilisateur concerné.

    Le manager tourne dans le thread principal asyncio ; les routes FastAPI sync
    appellent `publish()` via `call_soon_threadsafe` pour rester thread-safe.
    """

    def __init__(self) -> None:
        self._connections: Dict[str, List[asyncio.Queue]] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def connect(self, user_id: str) -> "asyncio.Queue[str]":
        q: asyncio.Queue[str] = asyncio.Queue()
        self._connections.setdefault(user_id, []).append(q)
        return q

    def disconnect(self, user_id: str, q: "asyncio.Queue[str]") -> None:
        try:
            self._connections[user_id].remove(q)
        except (KeyError, ValueError):
            pass

    def publish(self, user_id: str, event_type: str, data: dict) -> None:
        if not self._loop:
            return
        msg = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        for q in list(self._connections.get(user_id, [])):
            self._loop.call_soon_threadsafe(q.put_nowait, msg)


sse_manager = SSEManager()
