from typing import Annotated, Optional, Dict
from pydantic import BaseModel, EmailStr, StringConstraints, Field
from datetime import datetime


class UserFrom(BaseModel):
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)]
    username: Annotated[str, StringConstraints(min_length=3, max_length=16, strip_whitespace=True, pattern=r'^[A-Za-z][A-Za-z0-9_]*$')]
    nickname: Annotated[str, StringConstraints(min_length=2, max_length=50)]

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!",
                "username": "johndoe",
                "nickname": "John Doe"
            }
        }


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    username: str
    nickname: str
    avatar: Optional[str] = None
    status: int = 0
    joindate: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800,
                "user": {
                    "id": 123,
                    "email": "user@example.com",
                    "username": "johndoe",
                    "nickname": "John Doe",
                    "avatar": "https://example.com/avatar.jpg",
                    "status": 1,
                    "joindate": "2023-01-01T00:00:00"
                }
            }
        }


class RefreshTokenRequest(BaseModel):
    refresh_token: str

    class Config:
        json_schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }


class DataToken(BaseModel):
    user_id: Optional[int] = None
    exp: Optional[datetime] = None


class GroupCreate(BaseModel):
    name: Annotated[str, StringConstraints(min_length=4, max_length=20)]
    description: Optional[str] = Field(None, max_length=200)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "My Group",
                "description": "A group for discussing topics"
            }
        }


class MessageForm(BaseModel):
    content: Annotated[str, StringConstraints(min_length=1, max_length=400)]

    class Config:
        json_schema_extra = {
            "example": {
                "content": "Hello, world!"
            }
        }


class MessageEditForm(BaseModel):
    content: Annotated[str, StringConstraints(min_length=1, max_length=400)]

    class Config:
        json_schema_extra = {
            "example": {
                "content": "Updated message content"
            }
        }


class MessageDeleteResponse(BaseModel):
    success: bool
    message: str
    deleted_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Message deleted successfully",
                "deleted_at": "2024-01-01T12:00:00"
            }
        }


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: Annotated[str, StringConstraints(min_length=8, max_length=128)]

    class Config:
        json_schema_extra = {
            "example": {
                "old_password": "OldPass123!",
                "new_password": "NewSecurePass456!"
            }
        }