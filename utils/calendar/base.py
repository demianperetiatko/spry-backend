from abc import ABC, abstractmethod
from datetime import datetime


class BaseCalendarHandler(ABC):
    @abstractmethod
    def create_event(self, summary: str, start_date: datetime, end_date: datetime, description: str = "", location: str = ""):
        pass

    @abstractmethod
    def update_event(self, event_id: str, description: str):
        pass

    @abstractmethod
    def get_event_info(self, event_id: str):
        pass

    @abstractmethod
    def get_events(self, start_date: datetime, end_date: datetime):
        pass

    @abstractmethod
    def get_timezone(self):
        pass
