#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

USERS="${USERS:-20}"
ARTICLES="${ARTICLES:-100}"
FROM_SQLITE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --users)
      USERS="$2"
      shift 2
      ;;
    --articles)
      ARTICLES="$2"
      shift 2
      ;;
    --from-sqlite)
      FROM_SQLITE=true
      shift
      ;;
    *)
      echo "Użycie: $0 [--users N] [--articles N] [--from-sqlite]"
      exit 1
      ;;
  esac
done

echo "==> [1/3] Uruchamianie bazy PostgreSQL w Dockerze..."
docker compose up -d --wait postgres

echo "==> [2/3] Wykonywanie migracji Django w PostgreSQL..."
uv run --project app python app/my_medium/manage.py migrate --noinput

if [ "$FROM_SQLITE" = true ] && [ -f "app/my_medium/db.sqlite3" ]; then
  echo "==> [3/3] Przenoszenie danych z lokalnego pliku db.sqlite3 do PostgreSQL..."
  TMP_DUMP="$(mktemp /tmp/sqlite_dump_XXXXXX.json)"
  trap 'rm -f "$TMP_DUMP"' EXIT
  DATABASE_URL="sqlite:///$ROOT_DIR/app/my_medium/db.sqlite3" \
    uv run --project app python app/my_medium/manage.py dumpdata \
    auth.User blog.Tag blog.Article blog.Comment blog.Clap blog.TrendingArticle \
    --indent 2 -o "$TMP_DUMP"
  uv run --project app python app/my_medium/manage.py loaddata "$TMP_DUMP"
else
  echo "==> [3/3] Uzupełnianie bazy danymi (użytkownicy: $USERS, artykuły: $ARTICLES)..."
  uv run --project app python app/my_medium/manage.py seed --users "$USERS" --articles "$ARTICLES"
fi

echo "==> Gotowe! Baza PostgreSQL działa na localhost:5432/inkwell."
echo "    Konto administratora: login 'admin', hasło 'password'"
