from typing import Optional

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from sqlalchemy.orm import Session

from models import Organization
from models import OrganizationMember
from models import get_db
from service_views.organization.schemas.member import PaginatedMembersResponse
from service_views.organization.services.member import MemberService
from utils.middleware import get_auth_member
from utils.middleware import get_auth_organization
from utils.middleware import require_permission

router = APIRouter()


@router.get("/members/", response_model=PaginatedMembersResponse)
def get_organization_members(
    auth_member: OrganizationMember = Depends(get_auth_member),
    auth_organization: Organization = Depends(get_auth_organization),
    db: Session = Depends(get_db),
    search_query: Optional[str] = Query(None, description="Search by member name or email"),
    limit: int = Query(20, ge=1, le=100, description="Number of items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    _: None = require_permission("members:view"),
) -> PaginatedMembersResponse:
    member_service = MemberService(db)
    return member_service.get_organization_members(auth_member, auth_organization, search_query, limit, offset)
