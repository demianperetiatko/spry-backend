from fastapi import APIRouter, Depends

from src.modules.auth.dependency import get_auth_user
from src.modules.feedback.schemas import FeedbackRequest
from src.modules.feedback.service import FeedbackService, get_feedback_service
from src.modules.user.model import User

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("")
async def submit_feedback(
    body: FeedbackRequest,
    user: User = Depends(get_auth_user),
    service: FeedbackService = Depends(get_feedback_service),
) -> dict[str, str]:
    await service.submit_feedback(user, body.message)
    return {"status": "ok"}
