from django.contrib import admin
from django.urls import include, path

from . import health

urlpatterns = [
    path("healthz", health.healthz, name="healthz"),
    path("healthz/", health.healthz),
    path("readyz", health.readyz, name="readyz"),
    path("readyz/", health.readyz),
    path("", include("django_prometheus.urls")),
    path("admin/", admin.site.urls),
    path("", include("blog.urls", namespace="blog")),
]
