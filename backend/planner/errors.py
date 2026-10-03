from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler


class RoutingError(APIException):
    status_code = 502
    default_code = "routing_error"
    default_detail = "The routing provider could not complete this request."

    def __init__(self, detail=None, code=None, *, status_code=None):
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail=detail, code=code)


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    codes = exc.get_codes() if hasattr(exc, "get_codes") else "request_error"
    code = codes if isinstance(codes, str) else getattr(exc, "default_code", "request_error")
    detail = response.data
    if isinstance(detail, dict) and set(detail) == {"detail"}:
        detail = detail["detail"]

    return Response(
        {"error": {"code": str(code), "message": detail}},
        status=response.status_code,
        headers=response.headers,
    )
