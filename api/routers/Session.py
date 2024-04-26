from fastapi import Depends, APIRouter, WebSocket, WebSocketDisconnect, HTTPException,status
from sqlalchemy.orm import Session
from api.utils.crud import get_db, get_id_info
from api.utils.authentication import get_current_user
from api.utils.ext import broadcast , connected_clients
from api.models.models import User, Group, Message
from typing import List, Dict

router = APIRouter()


@router.websocket("/chat/{chatid}")
async def wsocket(
    chatid: int,
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    channel = get_id_info(session=db ,id=chatid)
    if channel is None:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Chat not found")
    await websocket.accept()
    if chatid not in connected_clients:
        try:
            connected_clients[chatid].append(websocket)
        except KeyError:
            connected_clients[chatid] = []
            connected_clients[chatid].append(websocket)
        print(connected_clients[chatid])
    try:
        while True:
            data = await websocket.receive_json()
            print(data)
            await broadcast(chatid ,data,connected_clients)
    except WebSocketDisconnect:
        print(connected_clients[chatid])
        if chatid in connected_clients and websocket in connected_clients[chatid]:
            connected_clients[chatid].remove(websocket)
    