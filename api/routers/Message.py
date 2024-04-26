from fastapi import (
    Depends,
    APIRouter,
    HTTPException,
    status,
    WebSocketDisconnect,
    WebSocket,
)
from sqlalchemy.orm import Session
from sqlalchemy import desc
from api.utils.crud import get_db, get_id_info, get_chat_id_info
from api.models.models import User, Message
from api.utils.authentication import get_current_user, verify_token_access
from api.utils.ext import generate_unique_id, broadcast
from api.schema.schema import MessageForm
from typing import Dict, List
import json
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(tags=['Message'])
connected_clients: Dict[int, List[WebSocket]] = {}


@router.websocket("/chat/{chatid}")
async def wsocket(
    chatid: int,
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    channel = get_id_info(session=db, id=chatid)
    if channel is None:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
        )
    await websocket.accept()
    if chatid not in connected_clients:
        connected_clients[chatid] = []
    if websocket not in connected_clients[chatid]:
        connected_clients[chatid].append(websocket)
        token = await websocket.receive_text()
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not Validate Credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        tdata = verify_token_access(token, credentials_exception)
        print(f"User added in ws {tdata}")
        pass
    try:
        while True:
            data = await websocket.receive_json()
            print(data)
            await broadcast(chatid, data, connected_clients)
    except WebSocketDisconnect:
        print(connected_clients[chatid])
        if chatid in connected_clients and websocket in connected_clients[chatid]:
            connected_clients[chatid].remove(websocket)


@router.post("/{id}/message")
async def send_message(
    id: int,
    content: MessageForm,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if get_chat_id_info(session=db, id=id):
        message = {
            "channelId": id,
            "content": content.dict(),
            "timeSent": datetime.now().isoformat(),
            "user": {
                "id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "avatar": user.avatar,
            },
        }
        mid = generate_unique_id(db)
        content = {"content": content.content}
        sendm = Message(id=mid, content=content, sender_id = user.id, group_id=id)
        db.add(sendm)
        db.commit()
        await broadcast(chatid=id, message=message, channel=connected_clients)
        return {"data": message}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat Not found"
        )


@router.get("/{id}/message/fetch")
async def fetch_message(id: int, db: Session = Depends(get_db)):
    messagesList = (
        db.query(Message, User)
        .join(User)
        .filter(Message.group_id == id)
        .order_by(desc(Message.timeSent))
        .limit(25)
        .all()
    )
    if not get_chat_id_info(id,db):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
        )
    messages = []
    for message, user in messagesList:
        data = {
            "channelId": id,
            "content": message.content,
            "timeSent": message.timeSent,
            "user": {
                "id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "avatar": user.avatar,
            },
        }
        messages.append(data)
    return messages
