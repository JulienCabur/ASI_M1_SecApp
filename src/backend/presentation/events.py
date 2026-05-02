import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from core.auth import get_current_user
from schema.auth_schema import UserInDB
from service.sse_service import sse_manager

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/stream")
async def event_stream(current_user: UserInDB = Depends(get_current_user)):
    """
    Flux SSE persistant par utilisateur authentifié.
    Événements émis : device_pending, device_approved, device_rejected, device_revoked.
    Un heartbeat (commentaire SSE) est envoyé toutes les 25s pour maintenir la connexion.
    """
    q = sse_manager.connect(current_user.id)

    async def generator():
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=25)
                    yield msg
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except (asyncio.CancelledError, Exception):
            pass
        finally:
            sse_manager.disconnect(current_user.id, q)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
