"""Custom DRF exception handler to preserve API contract: 400 responses use {"error": "..."}."""

from rest_framework.views import exception_handler


def _flatten_detail(detail):
    if isinstance(detail, list):
        return " ".join(_flatten_detail(d) for d in detail)
    if isinstance(detail, dict):
        return " ".join(_flatten_detail(v) for v in detail.values())
    return str(detail)


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None and response.status_code == 400:
        body = getattr(response, "data", None)
        if isinstance(body, dict):
            if "error" not in body:
                response.data = {"error": _flatten_detail(body)}
        else:
            response.data = {"error": _flatten_detail(body)}
    return response
