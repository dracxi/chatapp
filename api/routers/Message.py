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
from api.models.models import User, Message, Group, GroupMember
from api.utils.authentication import get_current_user, verify_token_access
from api.utils.ext import generate_unique_id, broadcast
from api.utils.websocket_manager import connection_manager
from api.schema.schema import MessageForm, MessageEditForm, MessageDeleteResponse
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
    reply_to_id: int = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = db.query(Group).filter(Group.id == id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
    
    membership = db.query(GroupMember).filter(
        GroupMember.group_id == id,
        GroupMember.member_id == user.id
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="You must be a member of this group to send messages"
        )
    
    reply_to_message = None
    if reply_to_id:
        reply_to_message = db.query(Message).filter(
            Message.id == reply_to_id,
            Message.group_id == id,
            Message.is_deleted == False
        ).first()
        if not reply_to_message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reply target message not found"
            )
    
    mid = generate_unique_id(db)
    message_content = {"content": content.content}
    
    sendm = Message(
        id=mid, 
        content=message_content, 
        sender_id=user.id, 
        group_id=id,
        reply_to_id=reply_to_id
    )
    db.add(sendm)
    db.commit()
    db.refresh(sendm)
    
    reply_info = None
    if reply_to_message:
        reply_info = {
            "id": reply_to_message.id,
            "content": reply_to_message.content,
            "sender": {
                "id": reply_to_message.sender.id,
                "username": reply_to_message.sender.username,
                "nickname": reply_to_message.sender.nickname,
            }
        }
    
    message = {
        "type": "new_message",
        "id": mid,
        "channelId": id,
        "content": message_content,
        "timeSent": sendm.timeSent.isoformat(),
        "is_edited": False,
        "edited_at": None,
        "reply_to": reply_info,
        "user": {
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "avatar": user.avatar,
        },
    }
    
    await broadcast(chatid=id, message=message, channel=connected_clients)
    await connection_manager.broadcast_to_group(id, message)
    return {"data": message}


@router.get("/{id}/message/fetch")
async def fetch_message(id: int, db: Session = Depends(get_db)):
    messagesList = (
        db.query(Message, User)
        .join(User)
        .filter(Message.group_id == id, Message.is_deleted == False)
        .order_by(desc(Message.timeSent))
        .limit(25)
        .all()
    )
    messages = []
    if not get_chat_id_info(id,db):
        return messages
    
    for message, user in messagesList:
        reply_info = None
        if message.reply_to_id:
            reply_to = db.query(Message, User).join(User).filter(
                Message.id == message.reply_to_id
            ).first()
            if reply_to:
                reply_message, reply_user = reply_to
                reply_info = {
                    "id": reply_message.id,
                    "content": reply_message.content,
                    "sender": {
                        "id": reply_user.id,
                        "username": reply_user.username,
                        "nickname": reply_user.nickname,
                    }
                }
        
        data = {
            "id": message.id,
            "channelId": id,
            "content": message.content,
            "timeSent": message.timeSent,
            "is_edited": message.is_edited,
            "edited_at": message.edited_at,
            "reply_to": reply_info,
            "user": {
                "id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "avatar": user.avatar,
            },
        }
        messages.append(data)
    return messages


@router.put("/message/{message_id}/edit")
async def edit_message(
    message_id: int,
    content: MessageEditForm,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Find the message
    message = db.query(Message).filter(
        Message.id == message_id,
        Message.is_deleted == False
    ).first()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Check if user is the sender
    if message.sender_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own messages"
        )
    
    # Update message
    message.content = {"content": content.content}
    message.is_edited = True
    message.edited_at = datetime.now()
    
    db.commit()
    db.refresh(message)
    
    # Prepare updated message for broadcast
    updated_message = {
        "type": "message_edited",
        "id": message.id,
        "channelId": message.group_id,
        "content": message.content,
        "timeSent": message.timeSent.isoformat(),
        "is_edited": message.is_edited,
        "edited_at": message.edited_at.isoformat(),
        "user": {
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "avatar": user.avatar,
        },
    }
    
    # Broadcast the edit to all connected clients
    await broadcast(chatid=message.group_id, message=updated_message, channel=connected_clients)
    await connection_manager.broadcast_to_group(message.group_id, updated_message)
    
    return {"data": updated_message}


@router.delete("/message/{message_id}")
async def delete_message(
    message_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Find the message
    message = db.query(Message).filter(
        Message.id == message_id,
        Message.is_deleted == False
    ).first()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Check if user is the sender
    if message.sender_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own messages"
        )
    
    # Soft delete the message
    message.is_deleted = True
    message.deleted_at = datetime.now()
    
    db.commit()
    
    # Prepare delete notification for broadcast
    delete_notification = {
        "type": "message_deleted",
        "id": message.id,
        "channelId": message.group_id,
        "deleted_at": message.deleted_at.isoformat(),
        "user": {
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "avatar": user.avatar,
        },
    }
    
    # Broadcast the deletion to all connected clients
    await broadcast(chatid=message.group_id, message=delete_notification, channel=connected_clients)
    await connection_manager.broadcast_to_group(message.group_id, delete_notification)
    
    return MessageDeleteResponse(
        success=True,
        message="Message deleted successfully",
        deleted_at=message.deleted_at
    )
