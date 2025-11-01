from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from api.db.database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    username = Column(String, unique=True, nullable=False)
    nickname = Column(String, nullable=False)
    bio = Column(String)
    avatar = Column(String, default="https://i.ibb.co/DpZXbnN/user-3296.png")
    status = Column(Integer, default=0)  # 0=offline, 1=online, 2=away, 3=busy
    last_seen = Column(DateTime, default=datetime.now)
    is_online = Column(Boolean, default=False)
    joindate = Column(DateTime, default=datetime.now)
    hashed_password = Column(String)
    is_deleted = Column(Boolean, default=False)

    sent_messages = relationship("Message", back_populates="sender")
    groups = relationship('GroupMember', back_populates='member')
    friends = relationship('Friend', back_populates='user', foreign_keys="[Friend.user_id]")
    sent_direct_messages = relationship('DirectMessage', back_populates='sender', foreign_keys='[DirectMessage.sender_id]')
    received_direct_messages = relationship('DirectMessage', back_populates='receiver', foreign_keys='[DirectMessage.receiver_id]')


class Friend(Base):
    __tablename__ = "friends"
    friendshipId = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    friend_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    status = Column(String, default='pending')  # 'pending', 'accepted', 'rejected', 'blocked'
    requester_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)  # Who sent the request
    is_blocked = Column(Boolean, default=False)
    nickname = Column(String, default=None)
    notes = Column(String, default=None)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship('User', foreign_keys=[user_id], back_populates='friends')
    friend = relationship('User', foreign_keys=[friend_id])
    requester = relationship('User', foreign_keys=[requester_id])


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
    joinId = Column(BigInteger, primary_key=True)
    member_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    group_id = Column(BigInteger, ForeignKey('groups.id'), nullable=False)
    is_admin = Column(Boolean, default=False)
    is_mod = Column(Boolean, default=False)
    joinDate = Column(DateTime, default=datetime.now)

    member = relationship('User', back_populates='groups')
    group = relationship('Group', back_populates='members')
    
    __table_args__ = (
        UniqueConstraint('member_id', 'group_id', name='unique_member_group'),
    )


class Message(Base):
    __tablename__ = "messages"
    id = Column(BigInteger, primary_key=True)
    content = Column(JSON, nullable=False)
    sender_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    group_id = Column(BigInteger, ForeignKey("groups.id"), nullable=False)
    reply_to_id = Column(BigInteger, ForeignKey("messages.id"), nullable=True)
    timeSent = Column(DateTime, default=datetime.now)
    is_edited = Column(Boolean, default=False)
    edited_at = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

    sender = relationship("User", back_populates="sent_messages")
    group = relationship("Group", back_populates="messages")
    reply_to = relationship("Message", remote_side=[id], backref="replies")


class DirectMessage(Base):
    __tablename__ = "direct_messages"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    content = Column(JSON, nullable=False)
    sender_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    reply_to_id = Column(BigInteger, ForeignKey("direct_messages.id"), nullable=True)
    timeSent = Column(DateTime, default=datetime.now)
    is_edited = Column(Boolean, default=False)
    edited_at = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_direct_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_direct_messages")
    reply_to = relationship("DirectMessage", remote_side=[id], backref="replies")


class LastSeen(Base):
    __tablename__ = 'lastseen'
    chat_id = Column(BigInteger, primary_key=True)
    member_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    chat_type = Column(String, nullable=False)  # 'direct' or 'group'
    last_seen_message_id = Column(BigInteger, nullable=True)  
    unread_count = Column(Integer, default=0)
    lastseen = Column(DateTime, default=datetime.now)

    member = relationship("User")

    last_seen_direct_message = relationship("DirectMessage", foreign_keys=[last_seen_message_id], primaryjoin="and_(LastSeen.last_seen_message_id==DirectMessage.id, LastSeen.chat_type=='direct')", viewonly=True)
    last_seen_group_message = relationship("Message", foreign_keys=[last_seen_message_id], primaryjoin="and_(LastSeen.last_seen_message_id==Message.id, LastSeen.chat_type=='group')", viewonly=True)
