from __future__ import annotations

import logging
from abc import ABC
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class Event(ABC):
    pass


class EventDispatcher:
    _instance: EventDispatcher | None = None
    _subscribers: dict[type[Event], list[Callable[[Event], Awaitable[None] | None]]]

    def __new__(cls) -> EventDispatcher:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscribers = {}
        return cls._instance

    def subscribe(
        self,
        event_type: type[Event],
        handler: Callable[[Event], Awaitable[None] | None],
    ) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed handler {handler.__name__} to event {event_type.__name__}")

    async def dispatch(self, event: Event) -> None:
        event_type = type(event)
        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            logger.debug(f"No handlers subscribed for event {event_type.__name__}")
            return

        logger.debug(f"Dispatching {event_type.__name__} to {len(handlers)} handler(s)")
        for handler in handlers:
            try:
                result = handler(event)
                if isinstance(result, Awaitable):
                    await result
            except Exception as e:
                logger.error(
                    f"Error in handler {handler.__name__} for event {event_type.__name__}: {e}",
                    exc_info=True,
                )


dispatcher = EventDispatcher()
