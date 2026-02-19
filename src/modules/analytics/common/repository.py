from __future__ import annotations

import uuid
from datetime import datetime
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.modules.analytics.common.calculator import MIN_MEETING_ATTENDEES
from src.modules.calendar.models import CalendarEvent, CalendarEventAttendee
from src.modules.enums import CalendarAttendeeResponseStatusEnum, CalendarEventStatusEnum
from src.modules.organization_member.model import OrganizationMember
from src.modules.organization_team.model import OrganizationTeamMember
from src.modules.user.model import User


class AnalyticsRepositoryBase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_events_for_period(
        self,
        user_calendar_ids: Sequence[uuid.UUID],
        start_date: datetime,
        end_date: datetime,
        include_attendees: bool = True,
        include_cancelled: bool = False,
    ) -> Sequence[CalendarEvent]:
        if not user_calendar_ids:
            return []

        statement = (
            select(CalendarEvent)
            .where(
                CalendarEvent.user_calendar_id.in_(user_calendar_ids),
                CalendarEvent.start_datetime <= end_date,
                CalendarEvent.end_datetime >= start_date,
            )
            .order_by(CalendarEvent.start_datetime)
        )

        if not include_cancelled:
            statement = statement.where(CalendarEvent.status != CalendarEventStatusEnum.CANCELLED)

        if include_attendees:
            statement = statement.options(selectinload(CalendarEvent.attendees))

        result = await self.session.execute(statement)
        return result.scalars().all()

    async def get_meeting_events_for_period(
        self,
        user_calendar_ids: Sequence[uuid.UUID],
        start_date: datetime,
        end_date: datetime,
        member_email: str,
        include_attendees: bool = True,
    ) -> Sequence[CalendarEvent]:
        if not user_calendar_ids:
            return []

        attendee_count_subq = (
            select(
                CalendarEventAttendee.calendar_event_id,
                func.count(CalendarEventAttendee.id).label("attendee_count"),
            )
            .group_by(CalendarEventAttendee.calendar_event_id)
            .subquery()
        )

        declined_subq = (
            select(CalendarEventAttendee.calendar_event_id)
            .where(
                CalendarEventAttendee.email == member_email,
                CalendarEventAttendee.response_status == CalendarAttendeeResponseStatusEnum.DECLINED,
            )
            .subquery()
        )

        statement = (
            select(CalendarEvent)
            .join(attendee_count_subq, CalendarEvent.id == attendee_count_subq.c.calendar_event_id)
            .where(
                CalendarEvent.user_calendar_id.in_(user_calendar_ids),
                CalendarEvent.start_datetime <= end_date,
                CalendarEvent.end_datetime >= start_date,
                CalendarEvent.status != CalendarEventStatusEnum.CANCELLED,
                CalendarEvent.hangout_link.isnot(None),
                attendee_count_subq.c.attendee_count >= MIN_MEETING_ATTENDEES,
                CalendarEvent.id.not_in(select(declined_subq.c.calendar_event_id).select_from(declined_subq)),
            )
            .order_by(CalendarEvent.start_datetime)
        )

        if include_attendees:
            statement = statement.options(selectinload(CalendarEvent.attendees))

        result = await self.session.execute(statement)
        return result.scalars().all()

    async def get_users_by_emails(self, emails: list[str]) -> Sequence[User]:
        if not emails:
            return []
        statement = select(User).where(User.email.in_(emails))
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def get_events_by_ids(
        self, event_ids: list[str], user_calendar_ids: Sequence[uuid.UUID] | None = None
    ) -> Sequence[CalendarEvent]:
        if not event_ids:
            return []

        found_events: list[CalendarEvent] = []
        found_ids: set[str] = set()

        if user_calendar_ids:
            statement = select(CalendarEvent).where(
                CalendarEvent.google_event_id.in_(event_ids),
                CalendarEvent.user_calendar_id.in_(user_calendar_ids),
            )
            result = await self.session.execute(statement)
            found_events = list(result.scalars().all())
            found_ids = {evt.google_event_id for evt in found_events}

        missing_ids = [eid for eid in event_ids if eid not in found_ids]
        if missing_ids:
            statement = select(CalendarEvent).where(CalendarEvent.google_event_id.in_(missing_ids))
            result = await self.session.execute(statement)
            additional_events = list(result.scalars().all())
            found_events.extend(additional_events)

        return found_events

    async def get_organization_member_emails(self, organization_id: uuid.UUID) -> set[str]:
        statement = (
            select(User.email)
            .join(OrganizationMember, User.id == OrganizationMember.user_id)
            .where(OrganizationMember.organization_id == organization_id)
        )
        result = await self.session.execute(statement)
        return set(result.scalars().all())

    async def get_team_member_emails(self, member_id: uuid.UUID) -> set[str]:
        team_ids_subq = (
            select(OrganizationTeamMember.team_id).where(OrganizationTeamMember.organization_member_id == member_id).subquery()
        )
        statement = (
            select(User.email)
            .join(OrganizationMember, User.id == OrganizationMember.user_id)
            .join(OrganizationTeamMember, OrganizationMember.id == OrganizationTeamMember.organization_member_id)
            .where(OrganizationTeamMember.team_id.in_(select(team_ids_subq.c.team_id)))
            .distinct()
        )
        result = await self.session.execute(statement)
        return set(result.scalars().all())
