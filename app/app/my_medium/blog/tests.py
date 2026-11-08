from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from blog.models import Article, Clap, Comment, Tag, TrendingArticle
from blog.tasks import compute_article_metrics, recompute_trending_articles


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="alice",
        email="alice@example.com",
        password="StrongPassword123!",
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username="bob",
        email="bob@example.com",
        password="StrongPassword123!",
    )


@pytest.fixture
def published_article(user):
    tag = Tag.objects.create(name="django")
    article = Article.objects.create(
        title="Scaling Django on Kubernetes",
        author=user,
        body="## Introduction\n\n" + ("word " * 420),
        status=Article.Status.PUBLISHED,
    )
    article.tags.add(tag)
    article.refresh_from_db()
    return article


# ---------------------------------------------------------------------------
# Stage 1 Tests: Health, Readiness & Metrics Endpoints
# ---------------------------------------------------------------------------


def test_healthz_does_not_touch_db(client):
    with patch("my_medium.health.check_database") as mock_db:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_db.assert_not_called()


@pytest.mark.django_db
def test_probes_bypass_allowed_hosts_for_kubelet_pod_ip(client, settings):
    settings.ALLOWED_HOSTS = ["inkwell.example.com"]
    # Normal route with Pod IP in Host header is rejected with 400 DisallowedHost
    normal_resp = client.get("/", HTTP_HOST="10.244.0.42:8000")
    assert normal_resp.status_code == 400

    # Kubelet probes with Pod IP in Host header bypass ALLOWED_HOSTS via HealthCheckMiddleware
    health_resp = client.get("/healthz", HTTP_HOST="10.244.0.42:8000")
    assert health_resp.status_code == 200

    ready_resp = client.get("/readyz", HTTP_HOST="10.244.0.42:8000")
    assert ready_resp.status_code == 200


@pytest.mark.django_db
def test_readyz_healthy(client):
    response = client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["checks"]["database"] == "ok"


@pytest.mark.django_db
def test_readyz_returns_503_when_db_fails(client):
    with patch("my_medium.health.check_database", side_effect=RuntimeError("DB down")):
        response = client.get("/readyz")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unavailable"
        assert data["checks"]["database"] == "error"


@pytest.mark.django_db
def test_readyz_returns_503_when_redis_fails(client):
    with patch("my_medium.health.check_redis", side_effect=ConnectionError("Redis down")):
        response = client.get("/readyz")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unavailable"
        assert data["checks"]["redis"] == "error"


@pytest.mark.django_db
def test_prometheus_metrics_endpoint(client, published_article):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"django_http_requests" in response.content
    assert b"django_db_execute_total" in response.content
    assert b"django_migrations_unapplied_total" in response.content
    assert b"django_migrations_applied_total" in response.content


# ---------------------------------------------------------------------------
# Stage 2 & 4 Tests: Models & Celery Tasks
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_article_slug_and_markdown_rendering(user):
    article = Article.objects.create(
        title="Hello Inkwell World!",
        author=user,
        body="**Bold text** and <script>alert(1)</script>",
        status=Article.Status.DRAFT,
    )
    assert article.slug == "hello-inkwell-world"
    rendered = article.render_markdown()
    assert "<strong>Bold text</strong>" in rendered
    assert "<script>" not in rendered


@pytest.mark.django_db
def test_compute_article_metrics_on_publish(published_article):
    # Eager Celery execution runs compute_article_metrics automatically on publish
    assert published_article.word_count == 422
    assert published_article.reading_time == 3


@pytest.mark.django_db
def test_compute_article_metrics_task_directly(user):
    from django.conf import settings

    assert settings.CELERY_BEAT_SCHEDULE_FILENAME == "/tmp/celerybeat-schedule"
    article = Article.objects.create(
        title="Direct Task Test",
        author=user,
        body=" ".join(["word"] * 200),
        status=Article.Status.DRAFT,
    )
    result = compute_article_metrics(article.id)
    article.refresh_from_db()
    assert result["status"] == "ok"
    assert article.word_count == 200
    assert article.reading_time == 1


@pytest.mark.django_db
def test_recompute_trending_articles_24h_window(user, other_user):
    art1 = Article.objects.create(
        title="Hot Story",
        author=user,
        body="Content 1",
        status=Article.Status.PUBLISHED,
    )
    art2 = Article.objects.create(
        title="Quiet Story",
        author=user,
        body="Content 2",
        status=Article.Status.PUBLISHED,
    )
    art_old = Article.objects.create(
        title="Old Story",
        author=user,
        body="Content 3",
        status=Article.Status.PUBLISHED,
    )

    # Recent interactions on art1 (2 claps + 1 comment = score 3)
    Clap.objects.create(article=art1, user=user)
    Clap.objects.create(article=art1, user=other_user)
    Comment.objects.create(article=art1, author=other_user, body="Great post!")

    # Recent interaction on art2 (1 clap = score 1)
    Clap.objects.create(article=art2, user=other_user)

    # Interaction older than 24h on art_old (should be excluded)
    old_clap = Clap.objects.create(article=art_old, user=user)
    Clap.objects.filter(pk=old_clap.pk).update(created_at=timezone.now() - timedelta(hours=30))

    count = recompute_trending_articles()
    assert count == 2

    trending = list(TrendingArticle.objects.order_by("rank"))
    assert len(trending) == 2
    assert trending[0].article == art1
    assert trending[0].rank == 1
    assert trending[0].score == 3
    assert trending[1].article == art2
    assert trending[1].rank == 2
    assert trending[1].score == 1


# ---------------------------------------------------------------------------
# Stage 3 Tests: Views, Auth, Search, Tags & HTMX Endpoints
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_home_feed_and_search(client, published_article, user):
    draft = Article.objects.create(
        title="Secret Draft Story",
        author=user,
        body="Unpublished draft body",
        status=Article.Status.DRAFT,
    )
    response = client.get(reverse("blog:home"))
    assert response.status_code == 200
    content = response.content.decode()
    assert published_article.title in content
    assert draft.title not in content

    # Search matching title
    search_resp = client.get(reverse("blog:search"), {"q": "Kubernetes"})
    assert published_article.title in search_resp.content.decode()

    # Search non-matching
    empty_resp = client.get(reverse("blog:search"), {"q": "NonExistentTermXYZ"})
    assert published_article.title not in empty_resp.content.decode()


@pytest.mark.django_db
def test_tag_page(client, published_article):
    response = client.get(reverse("blog:tag_detail", kwargs={"slug": "django"}))
    assert response.status_code == 200
    assert published_article.title in response.content.decode()


@pytest.mark.django_db
def test_author_profile_shows_drafts_only_to_owner(client, user, other_user, published_article):
    draft = Article.objects.create(
        title="My Private Draft",
        author=user,
        body="Draft text",
        status=Article.Status.DRAFT,
    )
    url = reverse("blog:author_profile", kwargs={"username": user.username})

    # Anonymous viewer does not see draft
    anon_resp = client.get(url)
    assert anon_resp.status_code == 200
    assert draft.title not in anon_resp.content.decode()

    # Author logged in sees draft
    client.force_login(user)
    owner_resp = client.get(url)
    assert draft.title in owner_resp.content.decode()


@pytest.mark.django_db
def test_article_create_edit_and_htmx_interactions(client, user):
    client.force_login(user)
    create_resp = client.post(
        reverse("blog:article_create"),
        {
            "title": "Twelve-Factor Django Apps",
            "body": "Stateless processes and env vars.",
            "status": Article.Status.PUBLISHED,
            "tags_input": "12factor, django, cloud",
        },
    )
    assert create_resp.status_code == 302
    article = Article.objects.get(title="Twelve-Factor Django Apps")
    assert article.tags.count() == 3

    # HTMX Clap
    clap_resp = client.post(
        reverse("blog:article_clap", kwargs={"slug": article.slug}),
        HTTP_HX_REQUEST="true",
    )
    assert clap_resp.status_code == 200
    article.refresh_from_db()
    assert article.claps_count == 1
    assert "1" in clap_resp.content.decode()

    # HTMX Comment
    comment_resp = client.post(
        reverse("blog:article_comment", kwargs={"slug": article.slug}),
        {"body": "Awesome 12-factor breakdown!"},
        HTTP_HX_REQUEST="true",
    )
    assert comment_resp.status_code == 200
    assert Comment.objects.filter(article=article).count() == 1
    assert "Awesome 12-factor breakdown!" in comment_resp.content.decode()


@pytest.mark.django_db
def test_user_registration_flow(client):
    resp = client.post(
        reverse("blog:register"),
        {
            "username": "newauthor",
            "first_name": "New",
            "last_name": "Author",
            "email": "newauthor@example.com",
            "password1": "ComplexPass987!",
            "password2": "ComplexPass987!",
        },
    )
    assert resp.status_code == 302
    assert User.objects.filter(username="newauthor").exists()


# ---------------------------------------------------------------------------
# Stage 5 Test: Management Seed Command
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_seed_management_command():
    call_command("seed", users=5, articles=12)
    assert User.objects.count() >= 5
    assert Article.objects.count() == 12
    assert Tag.objects.count() > 0
