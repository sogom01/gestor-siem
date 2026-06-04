from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.ws_manager import manager
from app.services.auth import decode_token

router = APIRouter(tags=["websocket"])


@router.websocket("/live-feed")
async def live_feed(ws: WebSocket, token: str = Query(...)):
    # Validar JWT antes de aceptar la conexión
    try:
        decode_token(token)
    except Exception:
        await ws.close(code=4001)
        return

    await manager.connect(ws)
    try:
        while True:
            # Mantener conexión viva; el server hace push
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(ws)
