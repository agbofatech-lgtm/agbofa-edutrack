import uuid


class RequestIdMiddleware:
    """Attach a generated request ID without trusting caller-controlled IDs."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = uuid.uuid4().hex
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        return response


class PrivateApiCacheMiddleware:
    """Prevent browsers and intermediaries from caching API/authentication data."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path_info == "/api" or request.path_info.startswith("/api/"):
            response["Cache-Control"] = (
                "private, no-store, no-cache, max-age=0, must-revalidate"
            )
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
        return response
