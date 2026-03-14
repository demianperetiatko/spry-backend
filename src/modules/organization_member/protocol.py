from __future__ import annotations

# TODO(multi-org): Delete this entire file — exists only for single-org hard-delete workaround.
# When multi-org is supported, delete_member should only remove the OrganizationMember record.
import uuid
from abc import ABC, abstractmethod

from src.modules.user.service import UserService


class MemberRemovalDelegate(ABC):
    @abstractmethod
    async def on_member_removal(self, user_id: uuid.UUID) -> None:
        raise NotImplementedError()


class UserHardDeletionAdapter(MemberRemovalDelegate):
    def __init__(self, user_service: UserService) -> None:
        self._user_service = user_service

    async def on_member_removal(self, user_id: uuid.UUID) -> None:
        await self._user_service.delete_user(user_id)
