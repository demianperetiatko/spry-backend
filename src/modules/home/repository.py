from __future__ import annotations

import uuid
from typing import Sequence

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.core.database.session import get_session
from src.modules.agenda.model import AgendaBeta
from src.modules.analytics.common.repository import AnalyticsRepositoryBase
from src.modules.calendar.models import CalendarCacheMetadata, CalendarEvent, OrganizationMemberCalendar, UserCalendar


class HomeRepository(AnalyticsRepositoryBase):
    async def get_calendar_ids_for_member(self, member_id: uuid.UUID) -> Sequence[uuid.UUID]:
        stmt = select(OrganizationMemberCalendar.user_calendar_id).where(
            OrganizationMemberCalendar.organization_member_id == member_id
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_member_timezone(self, member_id: uuid.UUID) -> str | None:
        stmt = (
            select(CalendarCacheMetadata.timezone)
            .join(UserCalendar, CalendarCacheMetadata.user_calendar_id == UserCalendar.id)
            .join(OrganizationMemberCalendar, OrganizationMemberCalendar.user_calendar_id == UserCalendar.id)
            .where(OrganizationMemberCalendar.organization_member_id == member_id)
            .order_by(UserCalendar.is_primary.desc(), CalendarCacheMetadata.updated_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_primary_calendar_for_member(self, member_id: uuid.UUID) -> OrganizationMemberCalendar | None:
        stmt = (
            select(OrganizationMemberCalendar)
            .join(UserCalendar, OrganizationMemberCalendar.user_calendar_id == UserCalendar.id)
            .where(OrganizationMemberCalendar.organization_member_id == member_id)
            .order_by(UserCalendar.is_primary.desc(), UserCalendar.created_at.asc())
            .limit(1)
            .options(
                joinedload(OrganizationMemberCalendar.user_calendar).joinedload(UserCalendar.cache_metadata),
                joinedload(OrganizationMemberCalendar.user_calendar).joinedload(UserCalendar.user_access_info),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_agenda_entry(self, member_id: uuid.UUID, event_id: str) -> AgendaBeta | None:
        stmt = select(AgendaBeta).where(
            AgendaBeta.organization_member_id == member_id,
            AgendaBeta.event_id == event_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_agenda_event_ids(self, member_id: uuid.UUID, event_ids: list[str]) -> set[str]:
        if not event_ids:
            return set()
        stmt = select(AgendaBeta.event_id).where(
            AgendaBeta.organization_member_id == member_id,
            AgendaBeta.event_id.in_(event_ids),
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def create_agenda_entry(self, member_id: uuid.UUID, event_id: str) -> AgendaBeta:
        agenda = AgendaBeta(organization_member_id=member_id, event_id=event_id)
        self.session.add(agenda)
        await self.session.flush()
        return agenda

    async def get_event_by_google_id(
        self, event_id: str, user_calendar_ids: Sequence[uuid.UUID] | None = None
    ) -> CalendarEvent | None:
        stmt = (
            select(CalendarEvent).options(selectinload(CalendarEvent.attendees)).where(CalendarEvent.google_event_id == event_id)
        )
        if user_calendar_ids:
            stmt = stmt.where(CalendarEvent.user_calendar_id.in_(user_calendar_ids))

        result = await self.session.execute(stmt.limit(1))
        return result.scalars().first()


async def get_home_repository(session: AsyncSession = Depends(get_session)) -> HomeRepository:
    return HomeRepository(session)
