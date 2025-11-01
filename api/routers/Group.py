from fastapi import Depends, APIRouter , HTTPException , status
from sqlalchemy.orm import Session
from api.utils.crud import get_db , get_chat_id_info , group_info
from api.models.models import User , Group , GroupMember
from api.utils.authentication import get_current_user
from api.utils.ext import generate_unique_id
from api.schema.schema import GroupCreate 

router = APIRouter(prefix='/group',tags=['Group'])
@router.post('/create')
async def create_group(formdata: GroupCreate, current_user=Depends(get_current_user), db: Session=Depends(get_db)):
    id = generate_unique_id(db)
    group = Group(
        id=id,
        name=formdata.name,
        description=formdata.description,
        owner_id=current_user.id
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return {
        'id':group.id,
        'name':group.name,
        'description':group.description,
        'owner':group.owner.id
    }

@router.post('/join')
async def join_group(group_id : int,user = Depends(get_current_user),db : Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found!")
    
    checkmember = db.query(GroupMember).filter(GroupMember.group_id == group_id, GroupMember.member_id == user.id).first()
    if checkmember:
        raise HTTPException(status_code=status.HTTP_208_ALREADY_REPORTED, detail="You are already a member")
    
    try:
        groupmember = GroupMember(
            joinId = generate_unique_id(db),
            member_id = user.id,
            group_id = group.id
        )
        db.add(groupmember)
        db.commit()
        db.refresh(groupmember)
        return {
            "message": "Successfully joined group",
            "group_id": group.id,
            "group_name": group.name,
            "member_id": user.id
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to join group")

@router.get('/list')
async def get_all_group(user = Depends(get_current_user),db: Session = Depends(get_db)):
    groups = db.query(Group).all()
    
    groups_with_membership = []
    for group in groups:
        is_member = db.query(GroupMember).filter(
            GroupMember.group_id == group.id,
            GroupMember.member_id == user.id
        ).first() is not None
        
        member_count = db.query(GroupMember).filter(GroupMember.group_id == group.id).count()
        
        group_data = {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "avatar": group.avatar,
            "dateCreated": group.dateCreated,
            "owner_id": group.owner_id,
            "is_member": is_member,
            "member_count": member_count
        }
        groups_with_membership.append(group_data)
    
    return groups_with_membership


@router.post('/leave/{group_id}')
async def leave_group(
    group_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    membership = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.member_id == user.id
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not a member of this group"
        )
    
    if group.owner_id == user.id:
        other_members = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.member_id != user.id
        ).count()
        
        if other_members > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot leave group as owner. Transfer ownership or delete the group."
            )
        else:
            db.delete(membership)
            db.delete(group)
            db.commit()
            return {"message": "Group deleted successfully"}
    
    db.delete(membership)
    db.commit()
    
    return {"message": "Left group successfully"}


@router.delete('/delete/{group_id}')
async def delete_group(
    group_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    if group.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only group owner can delete the group"
        )
    
    db.query(GroupMember).filter(GroupMember.group_id == group_id).delete()
    
    from api.models.models import Message
    db.query(Message).filter(Message.group_id == group_id).delete()
    
    db.delete(group)
    db.commit()
    
    return {"message": "Group deleted successfully"}
