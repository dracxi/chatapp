from fastapi import Depends, APIRouter , HTTPException ,status
from sqlalchemy import desc
from sqlalchemy.orm import Session
from api.utils.crud import get_db
from api.models.models import User, Message, Group, LastSeen, GroupMember
from api.utils.authentication import get_current_user

router = APIRouter(prefix='/user', tags=['Users'])

@router.get('/u/{username}')
async def get_user(username:str, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {
        'data':{
            'id':user.id,
            'username':user.username,
            'nickname':user.nickname,
            'avatar':user.avatar,
            'joinDate':user.joindate
        },
        'fetchedBy':current_user.id
    }
@router.get('/id/{id}')
async def get_user_by_id(id:int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {
        'data':{
            'id':user.id,
            'username':user.username,
            'nickname':user.nickname,
            'avatar':user.avatar,
            'joinDate':user.joindate
        },
        'fetchedBy':current_user.id
    }
@router.post('/test/update/')
async def user_update(data: dict , current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current_user.id).first()
    for key , value in data.items():
        if hasattr(user,key):
            setattr(user, key,value)
    db.commit()
    db.refresh(user)
    return user



@router.get('/{username}/chats')
async def group_chats(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    messages = db.query(Message).order_by(desc(Message.timeSent)).filter(Message.sender_id == user.id).all()
    groupmember = db.query(GroupMember).filter(GroupMember.member_id == user.id).all()
    groups = [gm.group for gm in groupmember]

    last_seen_records = db.query(LastSeen).filter(LastSeen.member_id == user.id).all()
    last_seen_map = {ls.chat_id: ls for ls in last_seen_records}

    chat_list = {'chats': []}
    chats = chat_list['chats']
    
    added_groups = set()

    for chat in messages:
        if chat.group_id not in added_groups:
            group = db.query(Group).filter(Group.id == chat.group_id).first()
            if not group:
                continue

            last_seen_record = last_seen_map.get(group.id, None)
            last_seen_message_id = last_seen_record.last_seen_message_id if last_seen_record else None

            unread_count = db.query(Message).filter(Message.group_id == group.id, Message.id > last_seen_message_id).count() if last_seen_message_id else 0

            data = {
                'id': chat.id,
                'content': chat.content,
                'user': {
                    'id': chat.sender.id,
                    'username': chat.sender.username,
                    'nickname': chat.sender.nickname,
                    'avatar': chat.sender.avatar,
                    'status': chat.sender.status
                },
                'group': {
                    'id': group.id,
                    'name': group.name,
                    'description': group.description,
                    'avatar': group.avatar
                },
                'timesent': chat.timeSent,
                'last_seen_message_id': last_seen_message_id,
                'unread_count': unread_count
            }
            chats.append(data)
            added_groups.add(chat.group_id)

    return chat_list