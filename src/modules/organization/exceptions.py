from starlette.status import HTTP_409_CONFLICT

from src.core.exceptions import ServiceException


class OrganizationMemberAlreadyExistsError(ServiceException):
    def __init__(self) -> None:
        super().__init__(
            message="User already in an organization",
            code="USER_IS_ALREADY_IN_ORGANIZATION",
            status_code=HTTP_409_CONFLICT,
        )


class OrganizationAlreadyExistsError(ServiceException):
    def __init__(self) -> None:
        super().__init__(
            message="Organization already exists",
            code="ORGANIZATION_ALREADY_EXISTS",
            status_code=HTTP_409_CONFLICT,
        )
