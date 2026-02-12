from __future__ import annotations

from starlette.status import HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND

from src.core.exceptions import ServiceException


class UserIsAdminError(ServiceException):
    def __init__(self):
        super().__init__(
            message="Cannot delete user with admin role",
            code="USER_IS_ADMIN_RESTRICTION",
            status_code=HTTP_403_FORBIDDEN,
        )


class UserNotFoundError(ServiceException):
    def __init__(self) -> None:
        super().__init__(
            message="User not found",
            code="USER_NOT_FOUND",
            status_code=HTTP_404_NOT_FOUND,
        )
