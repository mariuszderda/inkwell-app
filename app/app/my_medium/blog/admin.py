from django.contrib import admin

from .models import Article, Clap, Comment, Tag, TrendingArticle


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "author",
        "status",
        "word_count",
        "reading_time",
        "claps_count",
        "published_at",
        "created_at",
    ]
    list_filter = ["status", "created_at", "published_at", "tags"]
    search_fields = ["title", "body", "author__username"]
    prepopulated_fields = {"slug": ("title",)}
    raw_id_fields = ["author"]
    filter_horizontal = ["tags"]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["article", "author", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["body", "author__username", "article__title"]


@admin.register(Clap)
class ClapAdmin(admin.ModelAdmin):
    list_display = ["article", "user", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["user__username", "article__title"]


@admin.register(TrendingArticle)
class TrendingArticleAdmin(admin.ModelAdmin):
    list_display = ["rank", "article", "score", "claps_24h", "comments_24h", "computed_at"]
    ordering = ["rank"]
