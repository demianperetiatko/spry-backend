from starlette.status import HTTP_400_BAD_REQUEST


class NotFoundException(Exception):
    def __init__(self, message: str = "Entity not found") -> None:
        self.message = message
        super().__init__(self.message)


class ServiceException(Exception):
    def __init__(self, message: str, code: str | None = None, status_code: int = HTTP_400_BAD_REQUEST) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)
