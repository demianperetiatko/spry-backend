from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database.session import get_session
from src.modules.auth.dependency import OrganizationContext, get_auth_user, get_organization_context
from src.modules.auth.dependency import User as AuthUser
from src.modules.calendar.dependency import CalendarServiceDep
from src.modules.calendar.services.webhook_service import WebhookValidationError
from src.modules.calendar.tasks import background_incremental_sync_task, background_resync_organization_task
from src.modules.organization.repository import OrganizationRepositorySQLAlchemy
from src.shared.pubsub import publish_resync_organization

logger = logging.getLogger(__name__)

webhook_router = APIRouter(prefix="/integrations/google", tags=["google-calendar"])
router = APIRouter(prefix="/organizations/{organization_id}/integrations/google", tags=["google-calendar"])
admin_router = APIRouter(prefix="/admin/integrations/google", tags=["admin-calendar"])


@webhook_router.post("/webhook", response_model=None)
async def google_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    calendar_service: CalendarServiceDep,
) -> dict[str, str] | JSONResponse:
    try:
        headers = request.headers
        channel_id = headers.get("x-goog-channel-id")
        resource_id = headers.get("x-goog-resource-id")
        resource_state = headers.get("x-goog-resource-state")

        logger.info(f"Google webhook: channel={channel_id}, state={resource_state}")

        if resource_state == "sync":
            return {"status": "ok"}

        user_calendar_id = await calendar_service.validate_webhook_request(channel_id, resource_id)

        if user_calendar_id:
            logger.info(f"Triggering incremental sync for user calendar {user_calendar_id}")
            background_tasks.add_task(background_incremental_sync_task, user_calendar_id)
        else:
            logger.warning(f"Webhook validation failed: channel={channel_id}, resource={resource_id}")

        return {"status": "ok"}
    except WebhookValidationError as e:
        logger.warning(f"Webhook validation security error: {e}")
        return JSONResponse(status_code=403, content={"status": "forbidden", "error": str(e)})
    except Exception as e:
        logger.exception(f"Webhook processing error: {e}")
        return {"status": "error"}


@webhook_router.post("/resync")
async def manual_resync_calendar_for_user(
    user: Annotated[AuthUser, Depends(get_auth_user)],
    calendar_service: CalendarServiceDep,
) -> dict[str, object]:
    return await calendar_service.manual_resync_for_user(user.id)


@router.post("/resync-all")
async def manual_resync_calendar_for_organization(
    org_ctx: Annotated[OrganizationContext, Depends(get_organization_context)],
) -> dict[str, object]:
    publish_resync_organization(org_ctx.organization.id)
    return {"status": "ok", "message": "Resync triggered via worker"}


def verify_admin_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    if x_api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")


@admin_router.post(
    "/resync-all-organizations",
    dependencies=[Depends(verify_admin_api_key)],
)
async def resync_all_organizations(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    org_repo = OrganizationRepositorySQLAlchemy(session)
    organizations = await org_repo.get_all()

    for org in organizations:
        try:
            publish_resync_organization(org.id)
        except Exception:
            logger.warning(f"Pub/Sub unavailable for org {org.id}, queuing direct background task")
            background_tasks.add_task(background_resync_organization_task, org.id)

    logger.info(f"Queued calendar resync for {len(organizations)} organizations")
    return {"status": "ok", "organizations_queued": len(organizations)}
