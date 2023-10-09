import httpx


class Error(Exception):
    """Base exception for all ioka related errors."""


class TimeoutError(Error):
    """Raises on request timeout."""


class StatusError(Error):
    """Base class for all ioka response related errors."""

    status_code: httpx.codes
    message: str
    code: str

    def __init__(self, status_code: int, message: str, code: str) -> None:
        self.status_code = status_code
        self.message = message
        self.code = code

    def __str__(self) -> str:
        return f'{self.code}: {self.message}'

    def __repr__(self) -> str:
        return (
            f'{self.__class__.__name__}('
            f'status_code={self.status_code!r}, '
            f'message={self.message!r}, '
            f'code={self.code!r})'
        )


class ValidationError(StatusError):
    """Raises on validation errors."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(httpx.codes.BAD_REQUEST, message, code)


class UnauthenticatedError(StatusError):
    """Raises on unauthenticated access.

    Commonly on invalid credentials."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(httpx.codes.UNAUTHORIZED, message, code)


class UnauthorizedError(StatusError):
    """Raises on unauthorized access.

    Commonly if permission is not granted for the resource."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(httpx.codes.FORBIDDEN, message, code)


class NotFoundError(StatusError):
    """Raises if resource is not found."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(httpx.codes.NOT_FOUND, message, code)


class ConflictError(StatusError):
    """Raises if resource is already created or operation is impossible."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(httpx.codes.CONFLICT, message, code)


_status_error_mapping = {
    httpx.codes.BAD_REQUEST: ValidationError,
    httpx.codes.UNAUTHORIZED: UnauthenticatedError,
    httpx.codes.FORBIDDEN: UnauthorizedError,
    httpx.codes.NOT_FOUND: NotFoundError,
    httpx.codes.CONFLICT: ConflictError,
}


def get_status_error(
    status_code: int,
    message: str,
    code: str,
) -> StatusError:
    if status_code in _status_error_mapping:
        return _status_error_mapping[status_code](message, code)
    return StatusError(status_code, message, code)
