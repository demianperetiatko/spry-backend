from __future__ import annotations

import uuid
from typing import Sequence

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.core.database.session import get_session
from src.modules.agenda.model import AgendaBeta
from src.modules.analytics.common.repository import AnalyticsRepositoryBase
from src.modules.calendar.models import CalendarCacheMetadata, CalendarEvent, UserCalendar
from src.modules.organization_member.model import OrganizationMember
from src.modules.user.model import UserAccessInfo


class HomeRepository(AnalyticsRepositoryBase):
    async def get_calendar_ids_for_user(self, user_id: uuid.UUID) -> Sequence[uuid.UUID]:
        stmt = (
            select(UserCalendar.id)
            .join(UserAccessInfo, UserCalendar.user_access_info_id == UserAccessInfo.id)
            .where(UserAccessInfo.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_user_timezone(self, user_id: uuid.UUID) -> str | None:
        stmt = (
            select(CalendarCacheMetadata.timezone)
            .join(UserCalendar, CalendarCacheMetadata.user_calendar_id == UserCalendar.id)
            .join(UserAccessInfo, UserCalendar.user_access_info_id == UserAccessInfo.id)
            .where(UserAccessInfo.user_id == user_id)
            .order_by(UserCalendar.is_primary.desc(), CalendarCacheMetadata.updated_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_primary_calendar_for_user(self, user_id: uuid.UUID) -> UserCalendar | None:
        stmt = (
            select(UserCalendar)
            .join(UserAccessInfo, UserCalendar.user_access_info_id == UserAccessInfo.id)
            .where(UserAccessInfo.user_id == user_id)
            .order_by(UserCalendar.is_primary.desc(), UserCalendar.created_at.asc())
            .limit(1)
            .options(
                joinedload(UserCalendar.cache_metadata),
                joinedload(UserCalendar.user_access_info),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_agenda_entry(self, user_id: uuid.UUID, event_id: str) -> AgendaBeta | None:
        stmt = (
            select(AgendaBeta)
            .join(OrganizationMember, AgendaBeta.organization_member_id == OrganizationMember.id)
            .where(
                OrganizationMember.user_id == user_id,
                AgendaBeta.event_id == event_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_agenda_event_ids(self, user_id: uuid.UUID, event_ids: list[str]) -> set[str]:
        if not event_ids:
            return set()
        stmt = (
            select(AgendaBeta.event_id)
            .join(OrganizationMember, AgendaBeta.organization_member_id == OrganizationMember.id)
            .where(
                OrganizationMember.user_id == user_id,
                AgendaBeta.event_id.in_(event_ids),
            )
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def create_agenda_entry(self, user_id: uuid.UUID, event_id: str) -> AgendaBeta:
        stmt = select(OrganizationMember.id).where(OrganizationMember.user_id == user_id).limit(1)
        result = await self.session.execute(stmt)
        member_id = result.scalar_one_or_none()
        if member_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User has no organization memberships",
            )

        agenda = AgendaBeta(organization_member_id=member_id, event_id=event_id)
        self.session.add(agenda)
        await self.session.flush()
        return agenda

    async def get_user_calendar_by_id(self, user_calendar_id: uuid.UUID) -> UserCalendar | None:
        stmt = (
            select(UserCalendar)
            .where(UserCalendar.id == user_calendar_id)
            .options(joinedload(UserCalendar.user_access_info))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

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
