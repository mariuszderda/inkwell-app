import logging

import redis
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


def check_redis() -> bool:
    """Verify Redis connectivity when REDIS_URL is configured."""
    if not getattr(settings, "REDIS_URL", ""):
        return True
    client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
    return bool(client.ping())


def healthz(request):
    """Liveness probe: returns 200 OK without touching DB or Redis."""
    return JsonResponse({"status": "ok"}, status=200)


def readyz(request):
    """Readiness probe: checks DB and Redis connectivity; returns 503 if either fails."""
    checks = {"database": "ok", "redis": "ok"}
    is_ready = True

    try:
        check_database()
    except Exception as exc:
        logger.error("Readiness database check failed", extra={"error": str(exc)})
        checks["database"] = "error"
        is_ready = False

    try:
        if not check_redis():
            checks["redis"] = "error"
            is_ready = False
    except Exception as exc:
        logger.error("Readiness redis check failed", extra={"error": str(exc)})
        checks["redis"] = "error"
        is_ready = False

    status_code = 200 if is_ready else 503
    return JsonResponse(
        {"status": "ok" if is_ready else "unavailable", "checks": checks},
        status=status_code,
    )


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
