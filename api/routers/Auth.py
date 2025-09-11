from sqlite3 import IntegrityError
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm 
from fastapi.exceptions import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session
from api.schema.schema import UserFrom
from api.models.models import User
from api.utils.crud import get_db
from api.utils.authentication import create_access_token, get_current_user
from api.utils.ext import generate_unique_id
from passlib.context import CryptContext

router = APIRouter(prefix="/auth", tags=['Authentication'])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.post("/register")
async def register(userDetails: UserFrom, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(
        or_(User.email == userDetails.email, User.username == userDetails.username)
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already registered")

    hashed_password = pwd_context.hash(userDetails.password)
    user = User(
        email=userDetails.email,
        hashed_password=hashed_password,
        nickname=userDetails.nickname,
        username=userDetails.username,
        id=generate_unique_id(db)
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="User already exists")

    token = create_access_token({'user_id': user.id})
    return {"id": user.id, "token": token, "detail": "registered successfully"}


@router.post("/login")
async def login(userDetails: OAuth2PasswordRequestForm = Depends() , db : Session = Depends(get_db)):
    user = db.query(User).filter(User.email == userDetails.username or User.username == userDetails.username).first()
    if not user or not pwd_context.verify(userDetails.password,user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    token = create_access_token({'user_id':user.id})
    return {'id':user.id , 'token':token , 'detail':'login success'}

@router.get('/check')
async def check(current_user = Depends(get_current_user)):
    return current_user