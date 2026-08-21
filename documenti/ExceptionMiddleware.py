import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse


logger = logging.getLogger(__name__)

class ExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception:
            if settings.DEBUG:
                raise

            logger.exception(
                "Unhandled exception while processing %s %s",
                request.method,
                request.get_full_path(),
            )

            if request.accepts("application/json"):
                return JsonResponse(
                    {"detail": "Si è verificato un errore interno."},
                    status=500,
                )

            return HttpResponse(
                "Si è verificato un errore interno.",
                status=500,
                content_type="text/html; charset=utf-8",
            )