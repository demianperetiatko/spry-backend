from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import Form
from fastapi import UploadFile
from sqlalchemy.orm import Session

from models import OrganizationMember
from models import get_db
from models.repositories.organization_member_repository import OrganizationMemberRepository
from utils.gcp.bucket import upload_file
from utils.middleware import get_auth_member

router = APIRouter()


@router.get("/profile/")
def get_profile(member: OrganizationMember = Depends(get_auth_member)):
    return member


@router.put("/profile/")
def update_profile(
    name: str | None = Form(default=None),
    photo_file: UploadFile | None = File(None),
    member: OrganizationMember = Depends(get_auth_member),
    db: Session = Depends(get_db),
):
    org_member_repository = OrganizationMemberRepository(db)
    member.name = name
    if photo_file:
        member.photo_url = upload_file(photo_file, filename=str(member.id))
    org_member_repository.update(member)
