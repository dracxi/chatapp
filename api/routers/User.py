from fastapi import Depends, APIRouter , HTTPException ,status
from sqlalchemy.orm import Session
from api.utils.crud import get_db
from api.models.models import User
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