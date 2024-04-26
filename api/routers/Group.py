from fastapi import Depends, APIRouter
from sqlalchemy.orm import Session
from api.utils.crud import get_db
from api.models.models import User , Group
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

@router.get('/list')
async def get_all_group(user = Depends(get_current_user),db: Session = Depends(get_db)):
    groups = db.query(Group).all()
    return groups
