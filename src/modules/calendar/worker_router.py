from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from src.modules.calendar.tasks import background_resync_organization_task

logger = logging.getLogger(__name__)

worker_router = APIRouter(prefix="/worker", tags=["worker"])


@worker_router.post("/pubsub/resync-organization")
async def pubsub_resync_organization(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    body = await request.json()
    try:
        message_data = body["message"]["data"]
        payload = json.loads(base64.b64decode(message_data).decode("utf-8"))
        organization_id = uuid.UUID(payload["organization_id"])
    except Exception as e:
        logger.error(f"Failed to parse Pub/Sub message: {e}")
        return JSONResponse(status_code=400, content={"status": "error", "error": str(e)})

    logger.info(f"Received Pub/Sub resync-organization message for org={organization_id}")
    background_tasks.add_task(background_resync_organization_task, organization_id)
    return {"status": "ok"}