from typing import Optional, List
from models.repositories import BaseRepo
from models import OrganizationMember, OrganizationTeamMember, OrganizationTeamMemberTypeEnum
from models import OrganizationMemberCalendar


class OrganizationMemberRepository(BaseRepo[OrganizationMember]):
    def __init__(self, session):
        super().__init__(session, OrganizationMember)

    def update_member_cost(self, organization_id, average_cost: Optional[float]):
        formatted_cost = f"{average_cost:.2f}" if average_cost is not None else None
        self.session.query(OrganizationMember).filter(
            OrganizationMember.organization_id == organization_id
        ).update(
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
        return (
            self.session.query(OrganizationMember)
            .filter(OrganizationMember.email == email)
            .first()
        )

    def query_find_by_organization_id(self, organization_id):
        return (
            self.session.query(
                OrganizationMember.id,
                OrganizationMember.id.label('member_id'),
                OrganizationMember.name,
                OrganizationMember.photo_url,
                OrganizationMember.email,
                OrganizationMember.hourly_cost,
                OrganizationMember.status,
                OrganizationMember.google_refresh_token,
            )
            .filter(OrganizationMember.organization_id == organization_id)
        )

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
        return (
            self.session.query(OrganizationMemberCalendar)
            .filter(OrganizationMemberCalendar.member_id == member_id)
            .all()
        )
