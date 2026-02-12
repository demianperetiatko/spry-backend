from __future__ import annotations

from starlette.status import HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND

from src.core.exceptions import ServiceException


class TeamNotFoundError(ServiceException):
    def __init__(self) -> None:
        super().__init__(
            message="Team not found",
            status_code=HTTP_404_NOT_FOUND,
            code="TEAM_NOT_FOUND",
        )


class TeamPermissionError(ServiceException):
    def __init__(self) -> None:
        super().__init__(
            message="You do not have permission to perform this action",
            status_code=HTTP_403_FORBIDDEN,
            code="TEAM_PERMISSION_ERROR",
        )


class TeamValidationError(ServiceException):
    def __init__(self, message: str = "Team validation failed") -> None:
        super().__init__(
            message=message,
            status_code=HTTP_400_BAD_REQUEST,
            code="TEAM_VALIDATION_ERROR",
        )


class TeamMemberNotInOrganizationError(ServiceException):
    def __init__(self) -> None:
        super().__init__(
            message="One or more members do not belong to this organization",
            status_code=HTTP_400_BAD_REQUEST,
            code="TEAM_MEMBER_NOT_IN_ORGANIZATION",
        )
