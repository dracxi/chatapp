import random
from fastapi import WebSocket , HTTPException , status
from typing import Dict , List
from sqlalchemy.orm  import Session
from api.models.models import User , Message ,Group

def generate_unique_id(session: Session) -> int:
    while True:
        generated_id = random.randint(1000000000, 9999999999)
        existing_records = session.query(User.id).filter(User.id == generated_id). \
            union(session.query(Message.id).filter(Message.id == generated_id)). \
            union(session.query(Group.id).filter(Group.id == generated_id)).all()
        if not existing_records:
            return generated_id

async def broadcast(chatid:int , message: dict , channel:Dict[int,List[WebSocket]]):
    if chatid in channel:
        for channel in channel[chatid]:
            await channel.send_json(message)
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WebSocket connection not found for channel ID",
        )