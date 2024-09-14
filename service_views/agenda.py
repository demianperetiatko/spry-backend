from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from typing import List

from models import get_db, User, AgendaItem
from models.repositories.agenda_repository import AgendaItemRepository

from utils.auth import get_user

router = APIRouter()


@router.get('/agenda/')
def get_agenda_items(user: User = Depends(get_user), db: Session = Depends(get_db)):
    agenda_repository = AgendaItemRepository(db)
    agenda_items = agenda_repository.find_by_create_user_id(user.id)
    if agenda_items is None or len(agenda_items) == 0:
        return [{
            "title": "[Template name]",
            "description": "Display text from the template in the same way how it works in message preview in Gmail"
        } for _ in range(7)]
    return agenda_items


class AgendaRequest(BaseModel):
    title: str
    description: str


@router.post('/agenda/')
def create_agenda_item(agenda_info: AgendaRequest, user: User = Depends(get_user), db: Session = Depends(get_db)):
    agenda_repository = AgendaItemRepository(db)
    new_agenda = AgendaItem(
        title=agenda_info.title,
        description=agenda_info.description,
        create_user_id=user.id,
    )
    return agenda_repository.create(new_agenda)


@router.delete('/agenda/{agenda_id}/')
def delete_agenda_item(agenda_id: int, user: User = Depends(get_user), db: Session = Depends(get_db)):
    agenda_repository = AgendaItemRepository(db)
    agenda_item = agenda_repository.find_by_id(agenda_id)
    if agenda_item and agenda_item.create_user_id == user.id:
        agenda_repository.delete(agenda_item)
        return {"message": "Agenda item deleted successfully"}
    raise HTTPException(status_code=404, detail="Agenda item not found")
