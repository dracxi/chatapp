from typing import Annotated, Optional , Dict 
from pydantic import BaseModel, EmailStr, StringConstraints 

class UserFrom(BaseModel):
    email: EmailStr
    password: Annotated[str,StringConstraints(min_length=6,max_length=25)]
    username: Annotated[str,StringConstraints(min_length=3,max_length=16,strip_whitespace=True, pattern=r'^[A-z]')]
    nickname: Annotated[str,StringConstraints(min_length=4,max_length=25)]

class DataToken(BaseModel):
    id: Optional[str] = None
    expire: Optional[str] = None

class groupCreate(BaseModel):
    name:Annotated[str,StringConstraints(min_length=4,max_length=20)]
    description: Optional[str]

class MessageForm(BaseModel):
    content:Annotated[str,StringConstraints(max_length=400)]