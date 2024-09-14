from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from .user import User


from models import Base


class AgendaItem(Base):
    __tablename__ = 'agenda_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    create_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    create_user = relationship(User, backref='agenda_items_created')

    created_at = Column(DateTime, default=datetime.utcnow)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
