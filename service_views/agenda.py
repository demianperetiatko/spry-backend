from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from sqlalchemy.orm import Session

from pydantic import BaseModel, field_validator

from models import get_db, User, AgendaTemplate
from models.repositories.agenda_repository import AgendaTemplateRepository

from utils.auth import get_user

router = APIRouter()


@router.get('/agenda/')
def get_agenda_templates(
        template_id: Optional[int] = None,
        user: User = Depends(get_user),
        db: Session = Depends(get_db)
):
    agenda_repository = AgendaTemplateRepository(db)

    if template_id:
        template = agenda_repository.find_by_id_and_user_id(template_id, user.id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return template

    templates = agenda_repository.find_by_create_user_id(user.id)
    return templates


class AgendaRequest(BaseModel):
    title: str
    description: str

    @field_validator('title', 'description')
    def not_empty(cls, value, info):
        if not value or value.strip() == '':
            raise ValueError('This field can’t be empty')
        return value


@router.post('/agenda/')
def create_agenda_item(agenda_info: AgendaRequest, user: User = Depends(get_user), db: Session = Depends(get_db)):
    agenda_repository = AgendaTemplateRepository(db)
    new_template = AgendaTemplate(
        title=agenda_info.title,
        description=agenda_info.description,
        create_user_id=user.id,
    )
    return agenda_repository.create(new_template)


@router.put('/agenda/{agenda_id}/')
def update_agenda_item(
        agenda_id: int,
        agenda_info: AgendaRequest,
        user: User = Depends(get_user),
        db: Session = Depends(get_db)
):
    agenda_repository = AgendaTemplateRepository(db)
    agenda_item = agenda_repository.find_by_id(agenda_id)

    if agenda_item is None or agenda_item.create_user_id != user.id:
        raise HTTPException(status_code=404,
                            detail="Agenda item not found or you do not have permission to edit this item")

    agenda_item.title = agenda_info.title
    agenda_item.description = agenda_info.description

    agenda_repository.update(agenda_item)



@router.delete('/agenda/{agenda_id}/')
def delete_agenda_item(agenda_id: int, user: User = Depends(get_user), db: Session = Depends(get_db)):
    agenda_repository = AgendaTemplateRepository(db)
    agenda_item = agenda_repository.find_by_id(agenda_id)
    if agenda_item is None or agenda_item.create_user_id != user.id:
        raise HTTPException(status_code=404, detail="Agenda item not found")

    agenda_repository.delete(agenda_item)