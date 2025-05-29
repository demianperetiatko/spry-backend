import uuid
from typing import Type, TypeVar, Generic, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Query

T = TypeVar("T")


class BaseRepo(Generic[T]):
    def __init__(self, session, model: Type[T]):
        self.session = session
        self.model = model

    def create(self, obj: T) -> T:
        try:
            self.session.add(obj)
            self.session.commit()
            self.session.refresh(obj)
            return obj
        except SQLAlchemyError as e:
            self.session.rollback()
            raise e

    def delete(self, obj: T) -> None:
        try:
            self.session.delete(obj)
            self.session.commit()
        except SQLAlchemyError as e:
            self.session.rollback()
            raise e

    def update(self, obj: T) -> T:
        try:
            self.session.merge(obj)
            self.session.commit()
            self.session.refresh(obj)
            return obj
        except SQLAlchemyError as e:
            self.session.rollback()
            raise e

    def bulk_create(self, objs: list[T]) -> None:
        try:
            self.session.add_all(objs)
            self.session.commit()
        except SQLAlchemyError as e:
            self.session.rollback()
            raise e

    def bulk_update(self, objs: list[T]):
        try:
            self.session.bulk_save_objects(objs)
            self.session.commit()
        except SQLAlchemyError as e:
            self.session.rollback()
            raise e

    def delete_by_id(self, _id: str) -> bool:
        try:
            result = self.session.query(self.model).filter(self.model.id == _id).delete()
            self.session.commit()

            return result > 0
        except SQLAlchemyError as e:
            self.session.rollback()
            raise e

    def find(self, filters: list) -> Query:
        return self.session.query(self.model).filter(*filters)

    def find_by_id(self, _id) -> Optional[T]:
        filters = [self.model.id == _id]
        query = self.find(filters)
        return query.first()
