import logging
import math
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from .models import Article, TrendingArticle

logger = logging.getLogger(__name__)


@shared_task(name="blog.tasks.compute_article_metrics")
def compute_article_metrics(article_id: int) -> dict:
    """Compute word count and reading time (in minutes) when an article is published."""
    try:
        article = Article.objects.get(pk=article_id)
    except Article.DoesNotExist:
        logger.warning(
            "Article not found for metrics computation",
            extra={"article_id": article_id},
        )
        return {"status": "not_found", "article_id": article_id}

    words = (article.body or "").split()
    word_count = len(words)
    reading_time = max(1, math.ceil(word_count / 200)) if word_count > 0 else 1

    Article.objects.filter(pk=article_id).update(
        word_count=word_count,
        reading_time=reading_time,
    )
    logger.info(
        "Computed article metrics",
        extra={
            "article_id": article_id,
            "word_count": word_count,
            "reading_time": reading_time,
        },
    )
    return {
        "status": "ok",
        "article_id": article_id,
        "word_count": word_count,
        "reading_time": reading_time,
    }


@shared_task(name="blog.tasks.recompute_trending_articles")
def recompute_trending_articles(limit: int = 10) -> int:
    """
    Recompute trending articles based on claps + comments in the last 24 hours
    and store results in the TrendingArticle table.
    """
    cutoff = timezone.now() - timedelta(hours=24)

    candidates = (
        Article.published.annotate(
            claps_24h=Count("claps", filter=Q(claps__created_at__gte=cutoff), distinct=True),
            comments_24h=Count(
                "comments", filter=Q(comments__created_at__gte=cutoff), distinct=True
            ),
        )
        .annotate(score=F("claps_24h") + F("comments_24h"))
        .filter(score__gt=0)
        .order_by("-score", "-claps_24h", "-published_at")[:limit]
    )

    entries = [
        TrendingArticle(
            article=article,
            rank=index,
            score=article.score,
            claps_24h=article.claps_24h,
            comments_24h=article.comments_24h,
        )
        for index, article in enumerate(candidates, start=1)
    ]

    with transaction.atomic():
        TrendingArticle.objects.all().delete()
        if entries:
            TrendingArticle.objects.bulk_create(entries)

    logger.info("Recomputed trending articles", extra={"trending_count": len(entries)})
    return len(entries)
