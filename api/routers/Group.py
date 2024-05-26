from fastapi import Depends, APIRouter , HTTPException , status
from sqlalchemy.orm import Session
from api.utils.crud import get_db , get_chat_id_info , group_info
from api.models.models import User , Group , GroupMember
from api.utils.authentication import get_current_user
from api.utils.ext import generate_unique_id
from api.schema.schema import groupCreate 

router = APIRouter(prefix='/group',tags=['Group'])
@router.post('/create')
async def create_group(formdata: groupCreate, current_user=Depends(get_current_user), db: Session=Depends(get_db)):
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
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found!")
    checkmember = db.query(GroupMember).filter(GroupMember.group_id == group_id and GroupMember.member_id == user.id).first()
    if checkmember:
        return HTTPException(status_code=status.HTTP_208_ALREADY_REPORTED, detail="You are already a member")
    groupmember = GroupMember(
        joinId = generate_unique_id(db),
        member_id = user.id,
        group_id = group.id
    )
    db.add(groupmember)
    db.commit()
    db.refresh(groupmember)
    return groupmember

@router.get('/list')
async def get_all_group(user = Depends(get_current_user),db: Session = Depends(get_db)):
    groups = db.query(Group).all()
    return groups
