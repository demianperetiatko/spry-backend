from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Request, Depends
from fastapi.responses import JSONResponse

from src.modules.auth.dependency import OrganizationContext, get_organization_context, get_auth_user
from src.modules.auth.dependency import User as AuthUser
from src.modules.calendar.dependency import CalendarServiceDep
from src.modules.calendar.services.webhook_service import WebhookValidationError
from src.modules.calendar.tasks import background_incremental_sync_task, background_resync_organization_task

logger = logging.getLogger(__name__)

webhook_router = APIRouter(prefix="/integrations/google", tags=["google-calendar"])
router = APIRouter(prefix="/organizations/{organization_id}/integrations/google", tags=["google-calendar"])


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
    background_tasks: BackgroundTasks,
) -> dict[str, object]:
    background_tasks.add_task(background_resync_organization_task, org_ctx.organization.id)
    return {"status": "ok", "message": "Resync started in background"}
