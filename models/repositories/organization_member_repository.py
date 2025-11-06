from typing import List
from typing import Optional

from sqlalchemy.orm import Query
from sqlalchemy.orm import selectinload

from models import OrganizationMember
from models import OrganizationMemberCalendar
from models import OrganizationTeam
from models import OrganizationTeamMember
from models import OrganizationTeamMemberTypeEnum
from models.organization_member import CalendarTypeEnum
from models.organization_member import OrganizationMemberStatusEnum
from models.repositories import BaseRepo


class OrganizationMemberRepository(BaseRepo[OrganizationMember]):
    def __init__(self, session):
        super().__init__(session, OrganizationMember)

    def update_member_cost(self, organization_id, average_cost: Optional[float]):
        formatted_cost = f"{average_cost:.2f}" if average_cost is not None else None
        self.session.query(OrganizationMember).filter(OrganizationMember.organization_id == organization_id).update(
            {OrganizationMember.hourly_cost: formatted_cost}, synchronize_session=False
        )
        return self.session.commit()

    def find_by_member_id(self, organization_id, member_id) -> OrganizationMember:
        return (
            self.session.query(
                OrganizationMember.id,
                OrganizationMember.name,
                OrganizationMember.photo_url,
                OrganizationMember.email,
                OrganizationMember.hourly_cost,
                OrganizationMember.status,
            )
            .filter(OrganizationMember.id == member_id)
            .filter(OrganizationMember.organization_id == organization_id)
            .first()
        )

    def find_by_email(self, email: str) -> OrganizationMember:
        return self.session.query(OrganizationMember).filter(OrganizationMember.email == email.lower()).first()

    def query_find_by_organization_id(self, organization_id):
        return (
            self.session.query(
                OrganizationMember.id,
                OrganizationMember.id.label("member_id"),
                OrganizationMember.name,
                OrganizationMember.photo_url,
                OrganizationMember.email,
                OrganizationMember.hourly_cost,
                OrganizationMember.status,
                OrganizationMember.role,
            )
            .filter(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.status == OrganizationMemberStatusEnum.active,
            )
            .order_by(OrganizationMember.email)
        )

    def get_query_members_by_organization_id(
        self,
        organization_id: int,
        name: str | None = None,
        email: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[Query, int]:
        query = self.session.query(OrganizationMember).filter(OrganizationMember.organization_id == organization_id)

        if name:
            query = query.filter(OrganizationMember.name.ilike(f"%{name.strip()}%"))
        if email:
            query = query.filter(OrganizationMember.email.ilike(f"%{email.strip()}%"))

        total = query.count()

        if limit is not None:
            query = query.limit(limit)
        if offset is not None:
            query = query.offset(offset)

        query = query.options(selectinload(OrganizationMember.teams).joinedload(OrganizationTeamMember.team))

        return query, total

    def find_by_organization_id(self, organization_id):
        return self.query_find_by_organization_id(organization_id).all()

    def is_manager_of_organization(self, member_id) -> bool:
        res = (
            self.session.query(OrganizationTeamMember)
            .filter(OrganizationTeamMember.member_id == member_id)
            .filter(OrganizationTeamMember.type == OrganizationTeamMemberTypeEnum.manager)
            .first()
        )
        return bool(res)


class OrganizationMemberCalendarRepository(BaseRepo[OrganizationMemberCalendar]):
    def __init__(self, session):
        super().__init__(session, OrganizationMemberCalendar)

    def find_by_member_id(self, member_id) -> List[OrganizationMemberCalendar]:
        return self.session.query(OrganizationMemberCalendar).filter(OrganizationMemberCalendar.member_id == member_id).all()

    def find_by_member_email_and_type(
        self,
        member_id: str,
        calendar_email: str,
        calendar_type: CalendarTypeEnum,
    ) -> Optional[OrganizationMemberCalendar]:
        return (
            self.session.query(OrganizationMemberCalendar)
            .filter(
                OrganizationMemberCalendar.member_id == member_id,
                OrganizationMemberCalendar.calendar_email == calendar_email,
                OrganizationMemberCalendar.type == calendar_type,
            )
            .first()
        )
