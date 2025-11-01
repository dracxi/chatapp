from fastapi import Depends, APIRouter, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from api.utils.crud import get_db
from api.models.models import User, Friend
from api.utils.authentication import get_current_user
from api.utils.ext import generate_unique_id
from datetime import datetime

router = APIRouter(prefix='/friends', tags=['Friends'])


@router.post('/request/{user_id}')
async def send_friend_request(
    user_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send friend request to yourself"
        )
    
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    existing_friendship = db.query(Friend).filter(
        or_(
            and_(Friend.user_id == current_user.id, Friend.friend_id == user_id),
            and_(Friend.user_id == user_id, Friend.friend_id == current_user.id)
        )
    ).first()
    
    if existing_friendship:
        if existing_friendship.status == 'accepted':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already friends with this user"
            )
        elif existing_friendship.status == 'pending':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Friend request already sent"
            )
        elif existing_friendship.status == 'blocked':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot send friend request to blocked user"
            )
    
    friend_request = Friend(
        user_id=current_user.id,
        friend_id=user_id,
        requester_id=current_user.id,
        status='pending'
    )
    
    db.add(friend_request)
    db.commit()
    db.refresh(friend_request)
    
    return {
        "message": "Friend request sent successfully",
        "request_id": friend_request.friendshipId,
        "to_user": {
            "id": target_user.id,
            "username": target_user.username,
            "nickname": target_user.nickname
        }
    }


@router.post('/accept/{request_id}')
async def accept_friend_request(
    request_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    friend_request = db.query(Friend).filter(
        Friend.friendshipId == request_id,
        Friend.friend_id == current_user.id,
        Friend.status == 'pending'
    ).first()
    
    if not friend_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friend request not found"
        )
    
    friend_request.status = 'accepted'
    friend_request.updated_at = datetime.now()
    
    reciprocal_friendship = Friend(
        user_id=friend_request.friend_id,
        friend_id=friend_request.user_id,
        requester_id=friend_request.requester_id,
        status='accepted'
    )
    
    db.add(reciprocal_friendship)
    db.commit()
    
    return {
        "message": "Friend request accepted",
        "friend": {
            "id": friend_request.user.id,
            "username": friend_request.user.username,
            "nickname": friend_request.user.nickname,
            "avatar": friend_request.user.avatar
        }
    }


@router.post('/reject/{request_id}')
async def reject_friend_request(
    request_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reject a friend request"""
    friend_request = db.query(Friend).filter(
        Friend.friendshipId == request_id,
        Friend.friend_id == current_user.id,
        Friend.status == 'pending'
    ).first()
    
    if not friend_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friend request not found"
        )
    
    friend_request.status = 'rejected'
    friend_request.updated_at = datetime.now()
    db.commit()
    
    return {"message": "Friend request rejected"}


@router.get('/requests')
async def get_friend_requests(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get pending friend requests for current user"""
    requests = db.query(Friend).filter(
        Friend.friend_id == current_user.id,
        Friend.status == 'pending'
    ).all()
    
    request_list = []
    for request in requests:
        request_list.append({
            "id": request.friendshipId,
            "from_user": {
                "id": request.user.id,
                "username": request.user.username,
                "nickname": request.user.nickname,
                "avatar": request.user.avatar
            },
            "created_at": request.created_at.isoformat()
        })
    
    return {"requests": request_list}


@router.get('/list')
async def get_friends_list(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of accepted friends"""
    friends = db.query(Friend).filter(
        Friend.user_id == current_user.id,
        Friend.status == 'accepted'
    ).all()
    
    friends_list = []
    for friendship in friends:
        friends_list.append({
            "id": friendship.friendshipId,
            "friend": {
                "id": friendship.friend.id,
                "username": friendship.friend.username,
                "nickname": friendship.friend.nickname,
                "avatar": friendship.friend.avatar,
                "status": friendship.friend.status
            },
            "nickname": friendship.nickname,
            "notes": friendship.notes,
            "since": friendship.created_at.isoformat()
        })
    
    return {"friends": friends_list}


@router.delete('/remove/{friend_id}')
async def remove_friend(
    friend_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a friend (delete friendship)"""
    # Find both directions of the friendship
    friendships = db.query(Friend).filter(
        or_(
            and_(Friend.user_id == current_user.id, Friend.friend_id == friend_id),
            and_(Friend.user_id == friend_id, Friend.friend_id == current_user.id)
        ),
        Friend.status == 'accepted'
    ).all()
    
    if not friendships:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friendship not found"
        )
    
    # Delete both friendship records
    for friendship in friendships:
        db.delete(friendship)
    
    db.commit()
    
    return {"message": "Friend removed successfully"}


@router.post('/block/{user_id}')
async def block_user(
    user_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Block a user"""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot block yourself"
        )
    
    # Check if user exists
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Remove existing friendship if any
    existing_friendships = db.query(Friend).filter(
        or_(
            and_(Friend.user_id == current_user.id, Friend.friend_id == user_id),
            and_(Friend.user_id == user_id, Friend.friend_id == current_user.id)
        )
    ).all()
    
    for friendship in existing_friendships:
        db.delete(friendship)
    
    # Create block record
    block_record = Friend(
        user_id=current_user.id,
        friend_id=user_id,
        requester_id=current_user.id,
        status='blocked',
        is_blocked=True
    )
    
    db.add(block_record)
    db.commit()
    
    return {"message": "User blocked successfully"}


@router.post('/unblock/{user_id}')
async def unblock_user(
    user_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Unblock a user"""
    block_record = db.query(Friend).filter(
        Friend.user_id == current_user.id,
        Friend.friend_id == user_id,
        Friend.status == 'blocked'
    ).first()
    
    if not block_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Block record not found"
        )
    
    db.delete(block_record)
    db.commit()
    
    return {"message": "User unblocked successfully"}