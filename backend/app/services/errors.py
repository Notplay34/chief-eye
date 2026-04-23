"""Service-layer errors for domain operations."""


class ServiceError(Exception):
    """Domain/service error with an HTTP-friendly status code."""

    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code

