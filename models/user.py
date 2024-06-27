from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from models import Base

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100), nullable=False, unique=True)

    subordinates = relationship("Hierarchy", back_populates="manager", foreign_keys='Hierarchy.manager_id')
    managed_by = relationship("Hierarchy", back_populates="employee", foreign_keys='Hierarchy.employee_id')


class Hierarchy(Base):
    __tablename__ = 'hierarchy'

    id = Column(Integer, primary_key=True)
    manager_id = Column(Integer, ForeignKey('users.id'))
    employee_id = Column(Integer, ForeignKey('users.id'))

    manager = relationship("User", foreign_keys=[manager_id], back_populates="subordinates")
    employee = relationship("User", foreign_keys=[employee_id], back_populates="managed_by")
