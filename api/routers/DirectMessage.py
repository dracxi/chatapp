from fastapi import (
    Depends,
    APIRouter,
    HTTPException,
    status,
    WebSocketDisconnect,
    WebSocket,
)
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_
from api.utils.crud import get_db
from api.models.models import User, DirectMessage, Friend
from api.utils.authentication import get_current_user, verify_token_access
from api.utils.ext import generate_unique_id, broadcast
from api.utils.websocket_manager import connection_manager
from api.schema.schema import MessageForm, MessageEditForm, MessageDeleteResponse
from typing import Dict, List
import json
from datetime import datetime

router = APIRouter(prefix="/dm", tags=['Direct Messages'])
connected_dm_clients: Dict[str, List[WebSocket]] = {}


@router.websocket("/chat/{user_id}")
async def dm_websocket(
    user_id: int,
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        await websocket.close(code=4004)
        return
    
    await websocket.accept()
    
    # Create unique chat room ID for DM (smaller ID first for consistency)
    token = await websocket.receive_text()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not Validate Credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    current_user_data = verify_token_access(token, credentials_exception)
    current_user_id = current_user_data.get('user_id')
    
    chat_room_id = f"{min(current_user_id, user_id)}_{max(current_user_id, user_id)}"
    
    if chat_room_id not in connected_dm_clients:
        connected_dm_clients[chat_room_id] = []
    
    if websocket not in connected_dm_clients[chat_room_id]:
        connected_dm_clients[chat_room_id].append(websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            print(f"DM data received: {data}")
            await broadcast_dm(chat_room_id, data, connected_dm_clients)
    except WebSocketDisconnect:
        if chat_room_id in connected_dm_clients and websocket in connected_dm_clients[chat_room_id]:
            connected_dm_clients[chat_room_id].remove(websocket)


async def broadcast_dm(chat_room_id: str, message: dict, clients: Dict[str, List[WebSocket]]):
    if chat_room_id in clients:
        disconnected = []
        for websocket in clients[chat_room_id]:
            try:
                await websocket.send_json(message)
            except:
                disconnected.append(websocket)
        
        for ws in disconnected:
            clients[chat_room_id].remove(ws)


@router.post("/{receiver_id}/send")
async def send_direct_message(
    receiver_id: int,
    content: MessageForm,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    receiver = db.query(User).filter(User.id == receiver_id).first()
    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User not found"
        )
    
    message_id = generate_unique_id(db)
    content_data = {"content": content.content}
    
    dm = DirectMessage(
        id=message_id,
        content=content_data,
        sender_id=user.id,
        receiver_id=receiver_id
    )
    
    db.add(dm)
    db.commit()
    db.refresh(dm)
    
    # Prepare message for broadcast
    message_data = {
        "type": "new_message",
        "id": dm.id,
        "content": dm.content,
        "timeSent": dm.timeSent.isoformat(),
        "is_edited": dm.is_edited,
        "edited_at": None,
        "sender": {
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "avatar": user.avatar,
        },
        "receiver": {
            "id": receiver.id,
            "username": receiver.username,
            "nickname": receiver.nickname,
            "avatar": receiver.avatar,
        }
    }
    
    # Broadcast to DM room
    chat_room_id = f"{min(user.id, receiver_id)}_{max(user.id, receiver_id)}"
    await broadcast_dm(chat_room_id, message_data, connected_dm_clients)
    await connection_manager.broadcast_to_dm(chat_room_id, message_data)
    
    return {"data": message_data}


@router.get("/{user_id}/messages")
async def get_direct_messages(
    user_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    other_user = db.query(User).filter(User.id == user_id).first()
    if not other_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    messages = db.query(DirectMessage, User).join(
        User, DirectMessage.sender_id == User.id
    ).filter(
        or_(
            and_(DirectMessage.sender_id == user.id, DirectMessage.receiver_id == user_id),
            and_(DirectMessage.sender_id == user_id, DirectMessage.receiver_id == user.id)
        ),
        DirectMessage.is_deleted == False
    ).order_by(desc(DirectMessage.timeSent)).limit(50).all()
    
    message_list = []
    for message, sender in messages:
        data = {
            "id": message.id,
            "content": message.content,
            "timeSent": message.timeSent.isoformat(),
            "is_edited": message.is_edited,
            "edited_at": message.edited_at.isoformat() if message.edited_at else None,
            "sender": {
                "id": sender.id,
                "username": sender.username,
                "nickname": sender.nickname,
                "avatar": sender.avatar,
            },
            "receiver_id": message.receiver_id
        }
        message_list.append(data)
    
    return {"messages": message_list}


@router.get("/conversations")
async def get_conversations(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversations = db.query(DirectMessage).filter(
        or_(
            DirectMessage.sender_id == user.id,
            DirectMessage.receiver_id == user.id
        )
    ).order_by(desc(DirectMessage.timeSent)).all()
    
    conversation_map = {}
    for dm in conversations:
        partner_id = dm.receiver_id if dm.sender_id == user.id else dm.sender_id
        if partner_id not in conversation_map:
            conversation_map[partner_id] = dm
    
    conversation_list = []
    for partner_id, latest_message in conversation_map.items():
        partner = db.query(User).filter(User.id == partner_id).first()
        if partner:
            conversation_list.append({
                "partner": {
                    "id": partner.id,
                    "username": partner.username,
                    "nickname": partner.nickname,
                    "avatar": partner.avatar,
                },
                "latest_message": {
                    "id": latest_message.id,
                    "content": latest_message.content,
                    "timeSent": latest_message.timeSent.isoformat(),
                    "sender_id": latest_message.sender_id
                }
            })
    
    return {"conversations": conversation_list}


@router.put("/message/{message_id}/edit")
async def edit_direct_message(
    message_id: int,
    content: MessageEditForm,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Find the direct message
    dm = db.query(DirectMessage).filter(
        DirectMessage.id == message_id,
        DirectMessage.is_deleted == False
    ).first()
    
    if not dm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Check if user is the sender
    if dm.sender_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own messages"
        )
    
    # Update message
    dm.content = {"content": content.content}
    dm.is_edited = True
    dm.edited_at = datetime.now()
    
    db.commit()
    db.refresh(dm)
    
    # Get receiver info for broadcast
    receiver = db.query(User).filter(User.id == dm.receiver_id).first()
    
    # Prepare updated message for broadcast
    updated_message = {
        "type": "message_edited",
        "id": dm.id,
        "content": dm.content,
        "timeSent": dm.timeSent.isoformat(),
        "is_edited": dm.is_edited,
        "edited_at": dm.edited_at.isoformat(),
        "sender": {
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "avatar": user.avatar,
        },
        "receiver": {
            "id": receiver.id,
            "username": receiver.username,
            "nickname": receiver.nickname,
            "avatar": receiver.avatar,
        }
    }
    
    # Broadcast the edit to DM room
    chat_room_id = f"{min(user.id, dm.receiver_id)}_{max(user.id, dm.receiver_id)}"
    await broadcast_dm(chat_room_id, updated_message, connected_dm_clients)
    await connection_manager.broadcast_to_dm(chat_room_id, updated_message)
    
    return {"data": updated_message}


@router.delete("/message/{message_id}")
async def delete_direct_message(
    message_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Find the direct message
    dm = db.query(DirectMessage).filter(
        DirectMessage.id == message_id,
        DirectMessage.is_deleted == False
    ).first()
    
    if not dm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Check if user is the sender
    if dm.sender_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own messages"
        )
    
    # Soft delete the message
    dm.is_deleted = True
    dm.deleted_at = datetime.now()
    
    db.commit()
    
    # Get receiver info for broadcast
    receiver = db.query(User).filter(User.id == dm.receiver_id).first()
    
    # Prepare delete notification for broadcast
    delete_notification = {
        "type": "message_deleted",
        "id": dm.id,
        "deleted_at": dm.deleted_at.isoformat(),
        "sender": {
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "avatar": user.avatar,
        },
        "receiver": {
            "id": receiver.id,
            "username": receiver.username,
            "nickname": receiver.nickname,
            "avatar": receiver.avatar,
        }
    }
    
    # Broadcast the deletion to DM room
    chat_room_id = f"{min(user.id, dm.receiver_id)}_{max(user.id, dm.receiver_id)}"
    await broadcast_dm(chat_room_id, delete_notification, connected_dm_clients)
    await connection_manager.broadcast_to_dm(chat_room_id, delete_notification)
    
    return MessageDeleteResponse(
        success=True,
        message="Direct message deleted successfully",
        deleted_at=dm.deleted_at
    )


@router.delete("/conversation/{user_id}")
async def delete_conversation(
    user_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete entire conversation with a user"""
    # Check if other user exists
    other_user = db.query(User).filter(User.id == user_id).first()
    if not other_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Delete all messages between the two users
    deleted_count = db.query(DirectMessage).filter(
        or_(
            and_(DirectMessage.sender_id == user.id, DirectMessage.receiver_id == user_id),
            and_(DirectMessage.sender_id == user_id, DirectMessage.receiver_id == user.id)
        )
    ).delete()
    
    db.commit()
    
    return {
        "message": f"Conversation deleted successfully. {deleted_count} messages removed.",
        "deleted_messages": deleted_count
    }