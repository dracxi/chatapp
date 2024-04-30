from sqlalchemy import Column, Integer, String, DateTime , JSON, Boolean, BigInteger
from api.db.database import Base
from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship


class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    username = Column(String, unique=True, nullable=False)
    nickname = Column(String, nullable=False)
    bio = Column(String)
    avatar = Column(String, default="https://i.ibb.co/DpZXbnN/user-3296.png")
    status = Column(Integer , default=0)
    joindate = Column(DateTime, default=datetime.now)
    hashed_password = Column(String)
    is_deleted = Column(Boolean, default=False)

    sent_messages = relationship("Message", back_populates="sender")
    groups = relationship('GroupMember', back_populates='member')
    friends = relationship('Friend', back_populates='user', foreign_keys="[Friend.user_id]")


class Friend(Base):
    __tablename__ = "friends"
    friendshipId = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    friend_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    is_blocked = Column(Boolean, default=False)
    nickname = Column(String, default=None)
    notes = Column(String, default=None)

    user = relationship('User', foreign_keys=[user_id], back_populates='friends')
    friend = relationship('User', foreign_keys=[friend_id])


class Group(Base):
    __tablename__ = "groups"
    id = Column(BigInteger, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    avatar = Column(String, default="https://i.ibb.co/DpZXbnN/user-3296.png")
    dateCreated = Column(DateTime, default=datetime.now)
    owner_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)

    messages = relationship("Message", back_populates="group")
    members = relationship('GroupMember', back_populates='group')
    owner = relationship("User")


class GroupMember(Base):
    __tablename__ = "groupmembers"
    joinId = Column(BigInteger,primary_key=True)
    member_id = Column(BigInteger,ForeignKey("users.id"),nullable=False)
    group_id = Column(BigInteger,ForeignKey('groups.id'),nullable=False)
    is_admin = Column(Boolean,default=False)
    is_mod = Column(Boolean,default=False)
    joinDate = Column(DateTime, default=datetime.now)

    member = relationship('User', back_populates='groups')
    group = relationship('Group', back_populates='members')


class Message(Base):
    __tablename__ = "messages"
    id = Column(BigInteger, primary_key=True)
    content = Column(JSON, nullable=False)
    sender_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    group_id = Column(BigInteger, ForeignKey("groups.id"), nullable=False)
    timeSent = Column(DateTime, default=datetime.now)

    sender = relationship("User", back_populates="sent_messages")
    group = relationship("Group", back_populates="messages")