from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship

from models import Base


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100), nullable=False, unique=True)
    google_access_token = Column(Text)
    google_refresh_token = Column(Text)
    photo_url = Column(String(255))
