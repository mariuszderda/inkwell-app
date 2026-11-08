import math
import random
import uuid

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
from faker import Faker

from blog.models import Article, Clap, Comment, Tag
from blog.tasks import recompute_trending_articles

DEFAULT_TAGS = [
    "python",
    "django",
    "kubernetes",
    "devops",
    "architecture",
    "cloud",
    "backend",
    "databases",
    "postgresql",
    "redis",
    "celery",
    "security",
    "performance",
    "testing",
    "Linux",
]


class Command(BaseCommand):
    help = "Seed the database with fake users, articles, tags, comments, and claps."

    def add_arguments(self, parser):
        parser.add_argument(
            "--users",
            type=int,
            default=50,
            help="Number of users to generate (default: 50)",
        )
        parser.add_argument(
            "--articles",
            type=int,
            default=1000,
            help="Number of articles to generate (default: 1000)",
        )

    def handle(self, *args, **options):
        num_users = max(1, options["users"])
        num_articles = max(0, options["articles"])
        fake = Faker()

        self.stdout.write(f"Seeding {num_users} users and {num_articles} articles...")

        # 0. Ensure default superuser (admin / password) exists
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@example.com",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin_user.set_password("password")
            admin_user.save()

        # 1. Create tags
        tag_objs = []
        for name in DEFAULT_TAGS:
            clean_name = name.lower()
            tag, _ = Tag.objects.get_or_create(
                name=clean_name,
                defaults={"slug": slugify(clean_name)},
            )
            tag_objs.append(tag)

        # 2. Create users using a single pre-hashed password for speed
        hashed_pw = make_password("password123")
        users_to_create = []
        batch_suffix = uuid.uuid4().hex[:6]
        for i in range(num_users):
            username = f"{fake.user_name()}_{batch_suffix}_{i}"[:140]
            users_to_create.append(
                User(
                    username=username,
                    email=f"{username}@example.com",
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    password=hashed_pw,
                )
            )
        User.objects.bulk_create(users_to_create, ignore_conflicts=True)
        all_users = list(User.objects.order_by("-id")[:num_users])

        if not all_users or num_articles == 0:
            self.stdout.write(self.style.SUCCESS("Seeding completed."))
            return

        # 3. Create articles in bulk
        now = timezone.now()
        articles_to_create = []
        for i in range(num_articles):
            title = fake.sentence(nb_words=6).rstrip(".")
            paragraphs = fake.paragraphs(nb=random.randint(3, 6))
            body = f"## {fake.sentence(nb_words=4).rstrip('.')}\n\n" + "\n\n".join(paragraphs)
            words = len(body.split())
            reading_time = max(1, math.ceil(words / 200))
            slug = f"{slugify(title)[:220]}-{batch_suffix}-{i}"
            status = (
                Article.Status.PUBLISHED
                if random.random() < 0.9
                else Article.Status.DRAFT
            )
            published_at = now if status == Article.Status.PUBLISHED else None

            articles_to_create.append(
                Article(
                    title=title,
                    slug=slug,
                    author=random.choice(all_users),
                    body=body,
                    status=status,
                    word_count=words,
                    reading_time=reading_time,
                    claps_count=0,
                    published_at=published_at,
                )
            )

        Article.objects.bulk_create(articles_to_create, batch_size=500)
        created_articles = list(
            Article.objects.filter(slug__contains=f"-{batch_suffix}-")
        )

        # 4. Attach random tags to articles
        through_model = Article.tags.through
        through_entries = []
        for article in created_articles:
            chosen_tags = random.sample(tag_objs, k=random.randint(1, min(3, len(tag_objs))))
            for tag in chosen_tags:
                through_entries.append(through_model(article_id=article.id, tag_id=tag.id))
        through_model.objects.bulk_create(through_entries, ignore_conflicts=True, batch_size=1000)

        # 5. Generate sample claps and comments on a subset of published articles
        published_articles = [a for a in created_articles if a.status == Article.Status.PUBLISHED]
        sample_articles = published_articles[: min(50, len(published_articles))]
        claps_to_create = []
        comments_to_create = []
        for article in sample_articles:
            num_claps = random.randint(1, 8)
            for _ in range(num_claps):
                claps_to_create.append(
                    Clap(article=article, user=random.choice(all_users))
                )
            article.claps_count = num_claps

            for _ in range(random.randint(0, 3)):
                comments_to_create.append(
                    Comment(
                        article=article,
                        author=random.choice(all_users),
                        body=fake.paragraph(nb_sentences=2),
                    )
                )

        if claps_to_create:
            Clap.objects.bulk_create(claps_to_create, batch_size=500)
            Article.objects.bulk_update(sample_articles, ["claps_count"], batch_size=500)
        if comments_to_create:
            Comment.objects.bulk_create(comments_to_create, batch_size=500)

        recompute_trending_articles()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded {len(all_users)} users and {len(created_articles)} articles."
            )
        )
