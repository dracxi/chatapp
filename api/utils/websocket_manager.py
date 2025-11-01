from typing import Dict, List, Set
from fastapi import WebSocket
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.group_connections: Dict[int, List[WebSocket]] = {}
        self.dm_connections: Dict[str, List[WebSocket]] = {}
        self.user_connections: Dict[int, List[WebSocket]] = {}
        self.online_users: Set[int] = set()
        self.user_websocket_map: Dict[int, WebSocket] = {}

    async def connect_user(self, websocket: WebSocket, user_id: int):
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(websocket)
        
        self.online_users.add(user_id)
        self.user_websocket_map[user_id] = websocket
        
        await self.broadcast_user_status(user_id, True)
        logger.info(f"User {user_id} connected and marked online")

    async def connect_to_group(self, websocket: WebSocket, group_id: int, user_id: int):
        if group_id not in self.group_connections:
            self.group_connections[group_id] = []
        
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
            
        self.group_connections[group_id].append(websocket)
        self.user_connections[user_id].append(websocket)
        self.online_users.add(user_id)
        
        logger.info(f"User {user_id} connected to group {group_id}")

    async def connect_to_dm(self, websocket: WebSocket, chat_room_id: str, user_id: int):
        if chat_room_id not in self.dm_connections:
            self.dm_connections[chat_room_id] = []
            
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
            
        self.dm_connections[chat_room_id].append(websocket)
        self.user_connections[user_id].append(websocket)
        self.online_users.add(user_id)
        
        logger.info(f"User {user_id} connected to DM room {chat_room_id}")

    async def disconnect_user(self, websocket: WebSocket, user_id: int):
        if user_id in self.user_connections:
            if websocket in self.user_connections[user_id]:
                self.user_connections[user_id].remove(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
                self.online_users.discard(user_id)
                if user_id in self.user_websocket_map:
                    del self.user_websocket_map[user_id]
                await self.broadcast_user_status(user_id, False)
        
        logger.info(f"User {user_id} disconnected and marked offline")

    def disconnect_from_group(self, websocket: WebSocket, group_id: int, user_id: int):
        if group_id in self.group_connections:
            if websocket in self.group_connections[group_id]:
                self.group_connections[group_id].remove(websocket)
                
        if user_id in self.user_connections:
            if websocket in self.user_connections[user_id]:
                self.user_connections[user_id].remove(websocket)
            if not self.user_connections[user_id]:
                self.online_users.discard(user_id)
                
        logger.info(f"User {user_id} disconnected from group {group_id}")

    def disconnect_from_dm(self, websocket: WebSocket, chat_room_id: str, user_id: int):
        if chat_room_id in self.dm_connections:
            if websocket in self.dm_connections[chat_room_id]:
                self.dm_connections[chat_room_id].remove(websocket)
                
        if user_id in self.user_connections:
            if websocket in self.user_connections[user_id]:
                self.user_connections[user_id].remove(websocket)
            if not self.user_connections[user_id]:
                self.online_users.discard(user_id)
                
        logger.info(f"User {user_id} disconnected from DM room {chat_room_id}")

    async def broadcast_to_group(self, group_id: int, message: dict):
        if group_id not in self.group_connections:
            return
            
        disconnected = []
        for websocket in self.group_connections[group_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to group {group_id}: {e}")
                disconnected.append(websocket)
        
        for ws in disconnected:
            self.group_connections[group_id].remove(ws)

    async def broadcast_to_dm(self, chat_room_id: str, message: dict):
        if chat_room_id not in self.dm_connections:
            return
            
        disconnected = []
        for websocket in self.dm_connections[chat_room_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to DM {chat_room_id}: {e}")
                disconnected.append(websocket)
        
        for ws in disconnected:
            self.dm_connections[chat_room_id].remove(ws)

    async def send_to_user(self, user_id: int, message: dict):
        if user_id not in self.user_connections:
            return
            
        disconnected = []
        for websocket in self.user_connections[user_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to user {user_id}: {e}")
                disconnected.append(websocket)
        
        for ws in disconnected:
            self.user_connections[user_id].remove(ws)

    def get_online_users(self) -> List[int]:
        return [user_id for user_id, connections in self.user_connections.items() if connections]

    def is_user_online(self, user_id: int) -> bool:
        return user_id in self.online_users

    async def broadcast_user_status(self, user_id: int, is_online: bool):
        status_message = {
            "type": "user_status",
            "user_id": user_id,
            "is_online": is_online,
            "timestamp": datetime.now().isoformat()
        }
        
        disconnected = []
        for connected_user_id, websockets in self.user_connections.items():
            if connected_user_id != user_id:
                for websocket in websockets:
                    try:
                        await websocket.send_json(status_message)
                    except Exception as e:
                        logger.error(f"Error broadcasting status to user {connected_user_id}: {e}")
                        disconnected.append((connected_user_id, websocket))
        
        for user_id_disc, ws in disconnected:
            if user_id_disc in self.user_connections and ws in self.user_connections[user_id_disc]:
                self.user_connections[user_id_disc].remove(ws)

connection_manager = ConnectionManager()