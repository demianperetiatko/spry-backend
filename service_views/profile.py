from fastapi import Depends, APIRouter, File, UploadFile, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel

from models import get_db, OrganizationMember
from models.repositories.organization_repository import OrganizationMemberRepository

from utils.middleware import get_auth_member
from utils.gcp.bucket import upload_file

router = APIRouter()


@router.get("/profile/")
def get_profile(member: OrganizationMember = Depends(get_auth_member)):
    return member


@router.put("/profile/")
def update_profile(
        name: str | None = Form(default=None),
        photo_file: UploadFile | None = File(None),
        member: OrganizationMember = Depends(get_auth_member),
        db: Session = Depends(get_db)
):
    org_member_repository = OrganizationMemberRepository(db)
    member.name = name
    if photo_file:
        member.photo_url = upload_file(photo_file, filename=str(member.id))
    updated_user = org_member_repository.update(member)
