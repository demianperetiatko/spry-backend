from __future__ import annotations

import logging

from src.core.database.session import sessionmanager
from src.core.events import dispatcher
from src.modules.calendar.repository import CalendarRepository
from src.modules.calendar.tasks import task_connect_calendar_wrapper
from src.modules.invitation.events import InvitationAcceptedEvent

logger = logging.getLogger(__name__)


async def handle_invitation_accepted(event: InvitationAcceptedEvent) -> None:
    logger.info(
        f"Invitation accepted event received for user {event.user_id}, member {event.member_id}. Attempting to connect calendar."
    )

    async with sessionmanager.session() as session:
        calendar_repo = CalendarRepository(session)
        user_access_info = await calendar_repo.get_user_access_info(event.user_id)

        if not user_access_info:
            logger.debug(f"User {event.user_id} has no Google connection yet. Calendar will be connected after authentication.")
            return

        try:
            await task_connect_calendar_wrapper(
                user_id=event.user_id,
                member_id=event.member_id,
                user_email=event.user_email,
            )
            logger.info(f"Successfully triggered calendar connection for user {event.user_id}, member {event.member_id}")
        except Exception as e:
            logger.error(
                f"Failed to connect calendar for user {event.user_id}, member {event.member_id}: {e}",
                exc_info=True,
            )


def setup_calendar_subscriber() -> None:
    dispatcher.subscribe(InvitationAcceptedEvent, handle_invitation_accepted)
    logger.info("Registered calendar subscriber for InvitationAcceptedEvent")
