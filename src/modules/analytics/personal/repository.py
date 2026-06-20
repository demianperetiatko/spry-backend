from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.session import get_session
from src.modules.analytics.common.repository import AnalyticsRepositoryBase
from src.modules.calendar.models import OrganizationMemberCalendar

if TYPE_CHECKING:
    from collections.abc import Sequence


class PersonalAnalyticsRepository(AnalyticsRepositoryBase):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_calendar_ids_for_member(
        self,
        member_id: uuid.UUID,
    ) -> Sequence[uuid.UUID]:
        statement = select(OrganizationMemberCalendar.user_calendar_id).where(
            OrganizationMemberCalendar.organization_member_id == member_id
        )
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def get_calendar_ids_for_members(
        self,
        member_ids: Sequence[uuid.UUID],
    ) -> dict[uuid.UUID, list[uuid.UUID]]:
        """Batch lookup: returns {member_id: [calendar_id, ...]} in one query."""
        if not member_ids:
            return {}
        statement = select(
            OrganizationMemberCalendar.organization_member_id,
            OrganizationMemberCalendar.user_calendar_id,
        ).where(OrganizationMemberCalendar.organization_member_id.in_(member_ids))
        result = await self.session.execute(statement)
        mapping: dict[uuid.UUID, list[uuid.UUID]] = {}
        for member_id, calendar_id in result.all():
            mapping.setdefault(member_id, []).append(calendar_id)
        return mapping


async def get_personal_analytics_repository(
    session: AsyncSession = Depends(get_session),
) -> PersonalAnalyticsRepository:
    return PersonalAnalyticsRepository(session)
