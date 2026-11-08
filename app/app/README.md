# Inkwell

**Inkwell** is a 12-factor, Kubernetes-ready Medium-like blogging platform built with **Django 5** (Python 3.12), **Celery**, **Redis**, **PostgreSQL**, **HTMX**, and **Bootstrap 5**.

---

## Features

- **Authentication & Author Profiles**: Sign up, sign in, sign out, and dedicated `@username` profile pages displaying published stories (plus private drafts when viewing your own profile).
- **Markdown Articles & Tags**: Write and edit stories in Markdown (rendered safely to HTML via `markdown` + `bleach`), assign comma-separated tags, and toggle between `draft` and `published` states.
- **Feed, Tag Pages & Search**: Paginated home feed, tag-filtered feeds (`/tag/<slug>/`), and keyword search across titles and bodies (`/search/?q=...`).
- **HTMX Claps & Comments**: Interactive claps and comments updated dynamically without full-page reloads.
- **Async Processing (Celery + Redis)**:
  - **On publish**: `blog.tasks.compute_article_metrics` asynchronously computes word count and estimated reading time.
  - **Every 10 minutes (Celery Beat)**: `blog.tasks.recompute_trending_articles` ranks top stories based on claps + comments in the last 24 hours and stores them in the `TrendingArticle` table.
- **Kubernetes Observability & Stateless Design**:
  - `GET /healthz`: Liveness probe (`200 OK` without touching DB or Redis).
  - `GET /readyz`: Readiness probe (`200 OK` when DB and Redis are reachable; `503 Service Unavailable` otherwise).
  - `GET /metrics`: Prometheus metrics via `django-prometheus`.
  - Structured JSON logs written exclusively to `stdout`.
  - Static files served by **WhiteNoise** (`collectstatic` works at image build time with zero database/Redis access).

---

## Environment Variables

All configuration is injected via environment variables:

| Variable | Default (Dev Fallback) | Description |
| :--- | :--- | :--- |
| `SECRET_KEY` | `dev-insecure-secret-key...` | Django cryptographic secret key (**required in production**). |
| `DEBUG` | `False` | Enable Django debug mode (`True` / `False`). |
| `ALLOWED_HOSTS` | `*` | Comma-separated list of allowed hostnames (e.g. `inkwell.example.com,localhost`). |
| `CSRF_TRUSTED_ORIGINS` | `""` | Comma-separated list of trusted origins (e.g. `https://inkwell.example.com`). |
| `DATABASE_URL` | `postgres://postgres:postgres@localhost:5432/inkwell` | Database connection URL (set to `""` to fall back to local SQLite). |
| `REDIS_URL` | *Unset (runs Celery eagerly)* | Redis URL for Celery broker & backend (e.g. `redis://localhost:6379/0`). |
| `LOG_LEVEL` | `INFO` | Root, Django, and Celery JSON log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `WEB_CONCURRENCY` | `1` (Gunicorn default) | Number of Gunicorn worker processes per pod (read natively by Gunicorn). |

---

## Running Locally

All commands below assume your working directory is `app/my_medium` (or `app/` when installing dependencies).

### 1. Install Dependencies

Using `uv` (or `pip`):

```bash
cd app
uv sync
```

### 2. Mode A: Local Team Development (Docker PostgreSQL + Seed Script)

From the repository root, start PostgreSQL in Docker, run migrations, and seed sample articles in one command:

```bash
./setup_db.sh --users 20 --articles 100
```

Or migrate existing data from a local `db.sqlite3` file:

```bash
./setup_db.sh --from-sqlite
```

Then run the development server:

```bash
cd app/my_medium
export DEBUG=True
uv run python manage.py runserver 0.0.0.0:8000
```

### 3. Mode B: Production-Like Mode (PostgreSQL + Redis + Gunicorn + Celery)

```bash
cd app/my_medium
export SECRET_KEY="replace-with-strong-production-key"
export DEBUG="False"
export ALLOWED_HOSTS="localhost,127.0.0.1"
export DATABASE_URL="postgres://postgres:postgres@localhost:5432/inkwell"
export REDIS_URL="redis://localhost:6379/0"
export LOG_LEVEL="INFO"

# 1. Collect static files (can run during image build without DB/Redis access)
uv run python manage.py collectstatic --noinput

# 2. Run database migrations (run as a separate Job in Kubernetes before rollout)
uv run python manage.py migrate --noinput

# 3. Optional: Seed load-testing data (50 users, 1000 articles)
uv run python manage.py seed --users 50 --articles 1000
```

---

## Process Start Commands (for Kubernetes / Container Entrypoints)

Run each component as a separate stateless process from the `app/my_medium` directory:

| Process | Exact Command |
| :--- | :--- |
| **Web (Gunicorn)** | `gunicorn my_medium.wsgi:application --bind 0.0.0.0:8000 --access-logfile - --error-logfile -` |
| **Celery Worker** | `celery -A my_medium worker --loglevel=INFO` |
| **Celery Beat (Singleton: `replicas: 1`)** | `celery -A my_medium beat --loglevel=INFO --schedule /tmp/celerybeat-schedule` |
| **Migration Job** | `python manage.py migrate --noinput` |
| **Build-Time Static Assets** | `python manage.py collectstatic --noinput` |
| **Load-Test Data Seeding** | `python manage.py seed --users 50 --articles 1000` |

> **Kubernetes Deployment Notes for Celery Beat**:
> - Always run **Celery Beat** with `replicas: 1` (singleton) to avoid duplicate periodic task scheduling.
> - Beat writes its state file to `/tmp/celerybeat-schedule` (configured via `CELERY_BEAT_SCHEDULE_FILENAME` and `--schedule /tmp/celerybeat-schedule`), so the container works seamlessly with `readOnlyRootFilesystem: true` and an `emptyDir` mounted at `/tmp`.

---

## Testing & Linting

From the `app/` directory:

```bash
# Run pytest suite
uv run pytest

# Run ruff linter
uv run ruff check .
```
