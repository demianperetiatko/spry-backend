from __future__ import annotations

from starlette.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from src.core.exceptions import ServiceException


class InvitationNotFoundError(ServiceException):
    def __init__(self) -> None:
        super().__init__(
            status_code=HTTP_404_NOT_FOUND,
            message="Invitation not found",
            code="INVITATION_NOT_FOUND",
        )


class InvitationExpiredError(ServiceException):
    def __init__(self) -> None:
        super().__init__(
            status_code=HTTP_400_BAD_REQUEST,
            message="Invitation has expired",
            code="INVITATION_EXPIRED",
        )


class InvitationAcceptedError(ServiceException):
    def __init__(self) -> None:
        super().__init__(
            status_code=HTTP_400_BAD_REQUEST,
            message="Invitation already accepted",
            code="INVITATION_ALREADY_ACCEPTED",
        )


class UserAlreadyActiveInOrganizationError(ServiceException):
    def __init__(self) -> None:
        super().__init__(
            status_code=HTTP_400_BAD_REQUEST,
            message="User is already active in this organization",
            code="USER_ALREADY_ACTIVE_IN_ORGANIZATION",
        )


class OrganizationMemberNotFoundError(ServiceException):
    def __init__(self) -> None:
        super().__init__(
            status_code=HTTP_404_NOT_FOUND,
            message="Organization member not found for this invitation",
            code="ORGANIZATION_MEMBER_NOT_FOUND",
        )
