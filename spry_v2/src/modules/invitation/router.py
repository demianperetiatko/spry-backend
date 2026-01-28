from __future__ import annotations

from fastapi import APIRouter, Depends
from starlette.responses import RedirectResponse

from src.core.config import settings
from src.modules.invitation.service import InvitationService, get_invitation_service

router = APIRouter(prefix=settings.INVITATION_API_PREFIX, tags=["invitations"])


@router.get("/{token}")
async def accept_invitation(
    token: str,
    service: InvitationService = Depends(get_invitation_service),
) -> RedirectResponse:
    await service.accept_invitation(token)
    redirect_url = settings.get_invitation_accepted_redirect_url()
    return RedirectResponse(url=redirect_url)
