import logging

from django.conf import settings
from django.db import connections
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def check_database() -> bool:
    """Verify database connectivity by executing a lightweight query."""
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return True


def healthz(request):
    """Liveness probe: returns 200 OK without touching DB or Redis."""
    return JsonResponse({"status": "ok"}, status=200)


def readyz(request):
    """Readiness probe: pod jest gotowy, gdy odpowiada baza. Redis celowo pominięty."""
    try:
        check_database()
    except Exception as exc:
        logger.error("Readiness database check failed", extra={"error": str(exc)})
        return JsonResponse(
            {"status": "unavailable", "checks": {"database": "error"}}, status=503
        )
    return JsonResponse({"status": "ok", "checks": {"database": "ok"}}, status=200)


class HealthCheckMiddleware:
    """
    Intercepts /healthz and /readyz before SecurityMiddleware and CommonMiddleware
    so Kubernetes kubelet probes using the Pod IP in the Host header bypass
    Django's ALLOWED_HOSTS check (preventing 400 DisallowedHost).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in ("/healthz", "/healthz/"):
            return healthz(request)
        if request.path in ("/readyz", "/readyz/"):
            return readyz(request)
        return self.get_response(request)
