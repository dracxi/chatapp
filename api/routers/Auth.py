from sqlite3 import IntegrityError
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy import or_
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import bcrypt
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

from api.schema.schema import UserFrom, UserResponse, TokenResponse, RefreshTokenRequest, PasswordChangeRequest
from api.models.models import User
from api.utils.crud import get_db
from api.utils.authentication import (
    create_access_token, 
    create_refresh_token,
    get_current_user,
    verify_refresh_token
)
from api.utils.ext import generate_unique_id
from api.config.settings import settings

router = APIRouter(
    prefix="/auth", 
    tags=['Authentication'],
    responses={
        401: {"description": "Unauthorized"},
        400: {"description": "Bad Request"},
        422: {"description": "Validation Error"}
    }
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def validate_password(password: str) -> bool:
    if len(password) < settings.password_min_length:
        return False
    if len(password) > settings.password_max_length:
        return False
    
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'\d', password):
        return False
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False
    
    return True

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(userDetails: UserFrom, db: Session = Depends(get_db)):
    if not validate_password(userDetails.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long and contain uppercase, lowercase, digit, and special character"
        )
    
    existing_user = db.query(User).filter(
        or_(User.email == userDetails.email, User.username == userDetails.username)
    ).first()
    
    if existing_user:
        if existing_user.email == userDetails.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )

    hashed_password = hash_password(userDetails.password)
    
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User registration failed"
        )

    access_token = create_access_token(data={'user_id': user.id})
    refresh_token = create_refresh_token(data={'user_id': user.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            nickname=user.nickname,
            avatar=user.avatar,
            status=user.status,
            joindate=user.joindate
        )
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        or_(User.email == form_data.username, User.username == form_data.username)
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account has been deactivated"
        )
    
    access_token = create_access_token(data={'user_id': user.id})
    refresh_token = create_refresh_token(data={'user_id': user.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            nickname=user.nickname,
            avatar=user.avatar,
            status=user.status,
            joindate=user.joindate
        )
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    payload = verify_refresh_token(refresh_data.refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get('user_id')
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    access_token = create_access_token(data={'user_id': user.id})
    new_refresh_token = create_refresh_token(data={'user_id': user.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            nickname=user.nickname,
            avatar=user.avatar,
            status=user.status,
            joindate=user.joindate
        )
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        nickname=current_user.nickname,
        avatar=current_user.avatar,
        status=current_user.status,
        joindate=current_user.joindate
    )

@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    return {"message": "Successfully logged out"}


@router.post("/change-password")
async def change_password(
    password_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(password_data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    if password_data.old_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )
    
    if not validate_password(password_data.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters long and contain uppercase, lowercase, digit, and special character"
        )
    
    try:
        current_user.hashed_password = hash_password(password_data.new_password)
        db.commit()
        logger.info(f"Password changed for user {current_user.id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to change password for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )
    
    return {"message": "Password changed successfully"}