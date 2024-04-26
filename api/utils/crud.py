from api.db.database import SessionLocal
from sqlalchemy.orm import Session
from sqlalchemy import union
from api.models.models import User, Message , Group

def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

def get_id_info(session:Session, id):
    group = session.query(Group).get(id)
    if group:
        group.type = "group"
        return group
    user = session.query(User).get(id)
    if user:
        user.type = "user"
        return user
    message = session.query(Message).get(id)
    if message:
        message.type = "message"
        return message
    return None

def get_chat_id_info(id, session):
    group = session.query(Group).get(id)
    if group:
        group.type = "group"
        return group
    user = session.query(User).get(id)
    if user:
        user.type = "user"
        return user
    return None
