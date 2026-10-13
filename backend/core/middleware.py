import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from core.logging import request_id_context


class RequestIdMiddleware:
    """Generate an untrusted-header-independent request ID for logs and responses."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = uuid.uuid4().hex
        request.request_id = request_id  # type: ignore[attr-defined]
        token = request_id_context.set(request_id)
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            return response
        finally:
            request_id_context.reset(token)
