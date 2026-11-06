import logging
from django.db import IntegrityError
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response
    if isinstance(exc, IntegrityError):
        return Response({"detail": "These details conflict with an existing record. Check the ID and login name."}, status=409)
    logging.getLogger(__name__).exception("Portal request failed", exc_info=exc)
    return Response({"detail": "The request could not be completed. Please try again."}, status=500)
