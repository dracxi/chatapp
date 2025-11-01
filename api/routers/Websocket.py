from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlalchemy.orm import Session
from api.utils.crud import get_db
from api.models.models import User, Group, GroupMember
from api.utils.authentication import verify_token_access
from api.utils.websocket_manager import connection_manager
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(tags=['WebSocket'])


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: int,
    db: Session = Depends(get_db)
):
    """Main WebSocket endpoint for user connections"""
    try:
        # Accept the connection first
        await websocket.accept()
        
        # Wait for authentication token
        try:
            auth_data = await websocket.receive_text()
            auth_info = json.loads(auth_data)
            token = auth_info.get('token')
            
            if not token:
                await websocket.send_json({"error": "Authentication token required"})
                await websocket.close()
                return
            
            # Verify token
            credentials_exception = HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
            token_data = verify_token_access(token, credentials_exception)
            authenticated_user_id = token_data.user_id
            
            if authenticated_user_id != user_id:
                await websocket.send_json({"error": "Token user ID mismatch"})
                await websocket.close()
                return
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            await websocket.send_json({"error": "Authentication failed"})
            await websocket.close()
            return
        
        # Get user from database
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            await websocket.send_json({"error": "User not found"})
            await websocket.close()
            return
        
        # Connect user
        await connection_manager.connect_user(websocket, user_id)
        
        # Update user status in database
        user.is_online = True
        user.status = 1  # online
        db.commit()
        
        # Send connection confirmation
        await websocket.send_json({
            "type": "connection_established",
            "user_id": user_id,
            "message": "Connected successfully"
        })
        
        # Send current online users
        online_users = connection_manager.get_online_users()
        await websocket.send_json({
            "type": "online_users",
            "users": online_users
        })
        
        # Keep connection alive and handle messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle different message types
                message_type = message.get('type')
                
                if message_type == 'ping':
                    await websocket.send_json({"type": "pong"})
                elif message_type == 'join_group':
                    group_id = message.get('group_id')
                    if group_id:
                        await connection_manager.connect_to_group(websocket, group_id, user_id)
                elif message_type == 'leave_group':
                    group_id = message.get('group_id')
                    if group_id:
                        connection_manager.disconnect_from_group(websocket, group_id, user_id)
                elif message_type == 'join_dm':
                    chat_room_id = message.get('chat_room_id')
                    if chat_room_id:
                        await connection_manager.connect_to_dm(websocket, chat_room_id, user_id)
                elif message_type == 'typing':
                    # Handle typing indicators
                    chat_id = message.get('chat_id')
                    chat_type = message.get('chat_type')  # 'group' or 'dm'
                    is_typing = message.get('is_typing', False)
                    
                    typing_message = {
                        "type": "typing",
                        "user_id": user_id,
                        "chat_id": chat_id,
                        "chat_type": chat_type,
                        "is_typing": is_typing,
                        "user": {
                            "id": user.id,
                            "username": user.username,
                            "nickname": user.nickname
                        }
                    }
                    
                    if chat_type == 'group':
                        await connection_manager.broadcast_to_group(chat_id, typing_message)
                    elif chat_type == 'dm':
                        await connection_manager.broadcast_to_dm(str(chat_id), typing_message)
                
                elif message_type == 'message_read':
                    # Handle message read receipts
                    message_id = message.get('message_id')
                    chat_id = message.get('chat_id')
                    chat_type = message.get('chat_type')
                    
                    read_message = {
                        "type": "message_read",
                        "message_id": message_id,
                        "user_id": user_id,
                        "chat_id": chat_id,
                        "chat_type": chat_type,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    if chat_type == 'group':
                        await connection_manager.broadcast_to_group(chat_id, read_message)
                    elif chat_type == 'dm':
                        await connection_manager.broadcast_to_dm(str(chat_id), read_message)
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                break
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        # Disconnect user
        await connection_manager.disconnect_user(websocket, user_id)
        
        # Update user status in database
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.is_online = False
                user.status = 0  # offline
                from datetime import datetime
                user.last_seen = datetime.now()
                db.commit()
        except Exception as e:
            logger.error(f"Error updating user status on disconnect: {e}")


@router.get("/online-users")
async def get_online_users():
    """Get list of currently online users"""
    online_users = connection_manager.get_online_users()
    return {"online_users": online_users}


@router.get("/user-status/{user_id}")
async def get_user_status(user_id: int):
    """Check if a specific user is online"""
    is_online = connection_manager.is_user_online(user_id)
    return {"user_id": user_id, "is_online": is_online}


@router.websocket("/group/{group_id}")
async def group_websocket(
    group_id: int,
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    """WebSocket connection for group chats with typing indicators and presence"""
    try:
        await websocket.accept()
        
        # Get authentication token
        token_data = await websocket.receive_text()
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not Validate Credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        user_data = verify_token_access(token_data, credentials_exception)
        user_id = user_data.user_id
        
        # Verify user exists and has access to group
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            await websocket.close(code=4004)
            return
            
        # Check if user is member of the group
        membership = db.query(GroupMember).filter(
            GroupMember.member_id == user_id,
            GroupMember.group_id == group_id
        ).first()
        
        if not membership:
            await websocket.close(code=4003)
            return
        
        # Connect user to group
        await connection_manager.connect_to_group(websocket, group_id, user_id)
        
        # Notify others that user joined
        join_message = {
            "type": "user_joined",
            "user": {
                "id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "avatar": user.avatar,
            },
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_group(group_id, join_message)
        
        # Main message loop
        while True:
            data = await websocket.receive_json()
            await handle_group_message(group_id, user_id, data, db)
            
    except WebSocketDisconnect:
        connection_manager.disconnect_from_group(websocket, group_id, user_id)
        
        # Notify others that user left
        if user:
            leave_message = {
                "type": "user_left",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "nickname": user.nickname,
                    "avatar": user.avatar,
                },
                "timestamp": datetime.now().isoformat()
            }
            await connection_manager.broadcast_to_group(group_id, leave_message)
    except Exception as e:
        logger.error(f"WebSocket error in group {group_id}: {e}")
        await websocket.close(code=1011)


@router.websocket("/dm/{user_id}")
async def dm_websocket(
    user_id: int,
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    """WebSocket connection for direct messages with typing indicators and presence"""
    try:
        await websocket.accept()
        
        # Get authentication token
        token_data = await websocket.receive_text()
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not Validate Credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        current_user_data = verify_token_access(token_data, credentials_exception)
        current_user_id = current_user_data.user_id
        
        # Verify both users exist
        current_user = db.query(User).filter(User.id == current_user_id).first()
        other_user = db.query(User).filter(User.id == user_id).first()
        
        if not current_user or not other_user:
            await websocket.close(code=4004)
            return
        
        # Create chat room ID
        chat_room_id = f"{min(current_user_id, user_id)}_{max(current_user_id, user_id)}"
        
        # Connect user to DM
        await connection_manager.connect_to_dm(websocket, chat_room_id, current_user_id)
        
        # Notify other user that current user is online
        online_message = {
            "type": "user_online",
            "user": {
                "id": current_user.id,
                "username": current_user.username,
                "nickname": current_user.nickname,
                "avatar": current_user.avatar,
            },
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.send_to_user(user_id, online_message)
        
        # Main message loop
        while True:
            data = await websocket.receive_json()
            await handle_dm_message(chat_room_id, current_user_id, user_id, data, db)
            
    except WebSocketDisconnect:
        connection_manager.disconnect_from_dm(websocket, chat_room_id, current_user_id)
        
        # Notify other user that current user went offline
        if current_user:
            offline_message = {
                "type": "user_offline",
                "user": {
                    "id": current_user.id,
                    "username": current_user.username,
                    "nickname": current_user.nickname,
                    "avatar": current_user.avatar,
                },
                "timestamp": datetime.now().isoformat()
            }
            await connection_manager.send_to_user(user_id, offline_message)
    except Exception as e:
        logger.error(f"WebSocket error in DM {chat_room_id}: {e}")
        await websocket.close(code=1011)


async def handle_group_message(group_id: int, user_id: int, data: dict, db: Session):
    """Handle different types of messages in group chat"""
    message_type = data.get("type", "unknown")
    
    if message_type == "typing_start":
        typing_message = {
            "type": "typing_start",
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_group(group_id, typing_message)
        
    elif message_type == "typing_stop":
        typing_message = {
            "type": "typing_stop",
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_group(group_id, typing_message)
        
    elif message_type == "message_read":
        read_message = {
            "type": "message_read",
            "message_id": data.get("message_id"),
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_group(group_id, read_message)


async def handle_dm_message(chat_room_id: str, current_user_id: int, other_user_id: int, data: dict, db: Session):
    """Handle different types of messages in direct message chat"""
    message_type = data.get("type", "unknown")
    
    if message_type == "typing_start":
        typing_message = {
            "type": "typing_start",
            "user_id": current_user_id,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_dm(chat_room_id, typing_message)
        
    elif message_type == "typing_stop":
        typing_message = {
            "type": "typing_stop",
            "user_id": current_user_id,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_dm(chat_room_id, typing_message)
        
    elif message_type == "message_read":
        read_message = {
            "type": "message_read",
            "message_id": data.get("message_id"),
            "user_id": current_user_id,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.broadcast_to_dm(chat_room_id, read_message)