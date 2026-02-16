from __future__ import annotations

import uuid
from typing import Sequence

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.modules.analytics.common.repository import AnalyticsRepositoryBase
from src.core.database.session import get_session
from src.modules.calendar.models import OrganizationMemberCalendar
from src.modules.organization_member.model import OrganizationMember


class OrganizationAnalyticsRepository(AnalyticsRepositoryBase):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_calendar_ids_for_members(self, member_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[uuid.UUID]]:
        if not member_ids:
            return {}
        stmt = select(OrganizationMemberCalendar.organization_member_id, OrganizationMemberCalendar.user_calendar_id).where(
            OrganizationMemberCalendar.organization_member_id.in_(member_ids)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        mapping: dict[uuid.UUID, list[uuid.UUID]] = {}
        for member_id, calendar_id in rows:
            mapping.setdefault(member_id, []).append(calendar_id)
        return mapping

    async def filter_members_with_calendars(self, member_ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
        if not member_ids:
            return set()
        stmt = (
            select(OrganizationMemberCalendar.organization_member_id)
            .where(OrganizationMemberCalendar.organization_member_id.in_(member_ids))
            .distinct()
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def get_members_with_users(self, member_ids: Sequence[uuid.UUID]) -> list[OrganizationMember]:
        if not member_ids:
            return []
        stmt = (
            select(OrganizationMember).options(selectinload(OrganizationMember.user)).where(OrganizationMember.id.in_(member_ids))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


async def get_organization_analytics_repository(
    session: AsyncSession = Depends(get_session),
) -> OrganizationAnalyticsRepository:
    return OrganizationAnalyticsRepository(session)
