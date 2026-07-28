import logging

from rest_framework.views import exception_handler

logger = logging.getLogger("apps")


class DomainError(Exception):
    

    def __init__(self, message: str, code: str = "domain_error"):
        self.message = message
        self.code = code
        super().__init__(message)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if isinstance(exc, DomainError):
        from rest_framework.response import Response
        from rest_framework import status

        logger.warning("DomainError: %s", exc.message)
        return Response({"error": exc.code, "detail": exc.message}, status=status.HTTP_400_BAD_REQUEST)

    if response is not None:
        logger.warning("API error: %s | context=%s", response.data, context.get("view"))

    return response
