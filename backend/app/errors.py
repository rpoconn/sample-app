from typing import Any


# Raised anywhere in the app; app.main maps it onto the HTTP error envelope
class ApiError(Exception):
    status_code = 400
    code = "bad_request"
    headers: dict[str, str] | None = None

    def __init__(
        self,
        detail: str,
        *,
        code: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code or self.code
        self.context = context or {}


class Unauthorized(ApiError):
    status_code, code = 401, "unauthorized"
    headers = {"WWW-Authenticate": "Bearer"}


class Forbidden(ApiError):
    status_code, code = 403, "forbidden"


class NotFound(ApiError):
    status_code, code = 404, "not_found"


class Conflict(ApiError):
    status_code, code = 409, "conflict"


class PreconditionFailed(ApiError):
    status_code, code = 412, "version_mismatch"


class InvalidInput(ApiError):
    status_code, code = 422, "invalid_input"


class PreconditionRequired(ApiError):
    status_code, code = 428, "if_match_required"
