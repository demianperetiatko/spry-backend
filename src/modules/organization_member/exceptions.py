from __future__ import annotations

from starlette.status import HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND

from src.core.exceptions import ServiceException


class MemberNotFoundError(ServiceException):
    def __init__(self) -> None:
        super().__init__(
            message="Member not found",
            code="Member_NOT_FOUND",
            status_code=HTTP_404_NOT_FOUND,
        )


class MemberAlreadyExistsError(ServiceException):
    def __init__(self, existing_emails: list[str]) -> None:
        super().__init__(
            message="Some members already exist in this organization",
            code="MEMBER_ALREADY_EXISTS",
            status_code=HTTP_400_BAD_REQUEST,
        )
        self.existing_emails = existing_emails


class CannotEditMemberError(ServiceException):
    def __init__(self) -> None:
        super().__init__(
            message="You do not have permission to perform this action",
            code="CANNOT_EDIT_MEMBER",
            status_code=HTTP_403_FORBIDDEN,
        )


class MemberAlreadyActiveError(ServiceException):
    def __init__(self) -> None:
        super().__init__(
            message="Member is already active in this organization. Cannot resend invitation to active members.",
            code="MEMBER_ALREADY_ACTIVE",
            status_code=HTTP_400_BAD_REQUEST,
        )


class OrganizationCurrencyNotConfiguredError(ServiceException):
    def __init__(self) -> None:
        super().__init__(
            message="Organization currency is not configured",
            code="ORG_CURRENCY_NOT_CONFIGURED",
            status_code=HTTP_400_BAD_REQUEST,
        )


class MemberNotActiveError(ServiceException):
    def __init__(self) -> None:
        super().__init__(
            message="Member is not active",
            code="MEMBER_NOT_ACTIVE",
            status_code=HTTP_400_BAD_REQUEST,
        )
