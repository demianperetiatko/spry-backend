from sqlalchemy.orm import Session

from models.repositories.organization_member_repository import OrganizationMemberRepository


def get_user_profile(email: str, db: Session):
    user_id = None
    name = None
    photo_url = None
    user_repository = OrganizationMemberRepository(db)
    user = user_repository.find_by_email(email)
    if user:
        user_id = user.id
        name = user.name
        photo_url = user.photo_url

    return {"id": user_id, "name": name, "email": email, "photo_url": photo_url}
