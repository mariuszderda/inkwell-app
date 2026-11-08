import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_medium.settings")

app = Celery("inkwell")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "recompute-trending-articles-every-10-mins": {
        "task": "blog.tasks.recompute_trending_articles",
        "schedule": crontab(minute="*/10"),
    },
}
