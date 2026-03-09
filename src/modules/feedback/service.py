from __future__ import annotations

from fastapi import Depends

from src.modules.feedback.model import Feedback
from src.modules.feedback.repository import FeedbackRepository, get_feedback_repository
from src.modules.user.model import User
from src.shared.email import EmailService, get_email_service


class FeedbackService:
    def __init__(
        self,
        feedback_repo: FeedbackRepository,
        email_service: EmailService,
    ) -> None:
        self.feedback_repo = feedback_repo
        self.email_service = email_service

    async def submit_feedback(self, user: User, message: str) -> None:
        feedback = Feedback(
            user_id=user.id,
            message=message,
        )
        await self.feedback_repo.create(feedback)
        await self.email_service.send_feedback_notification(
            email=user.email,
            user_name=user.name or user.email,
            message=message,
        )


async def get_feedback_service(
    feedback_repo: FeedbackRepository = Depends(get_feedback_repository),
    email_service: EmailService = Depends(get_email_service),
) -> FeedbackService:
    return FeedbackService(
        feedback_repo=feedback_repo,
        email_service=email_service,
    )
