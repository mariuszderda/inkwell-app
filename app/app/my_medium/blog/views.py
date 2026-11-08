from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import ArticleForm, BootstrapAuthenticationForm, CommentForm, UserRegistrationForm
from .models import Article, Clap, Tag, TrendingArticle


def _sidebar_context() -> dict:
    trending = TrendingArticle.objects.select_related("article", "article__author").order_by(
        "rank"
    )[:5]
    popular_tags = (
        Tag.objects.annotate(
            article_count=Count("articles", filter=Q(articles__status=Article.Status.PUBLISHED))
        )
        .filter(article_count__gt=0)
        .order_by("-article_count", "name")[:15]
    )
    return {
        "trending_entries": trending,
        "popular_tags": popular_tags,
    }


def home(request):
    query = request.GET.get("q", "").strip()
    queryset = (
        Article.published.select_related("author")
        .prefetch_related("tags")
        .annotate(comments_count=Count("comments", distinct=True))
        .order_by("-published_at", "-created_at")
    )
    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(body__icontains=query))

    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_obj": page_obj,
        "articles": page_obj.object_list,
        "search_query": query,
        **_sidebar_context(),
    }
    return render(request, "blog/home.html", context)


def tag_detail(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    queryset = (
        Article.published.filter(tags=tag)
        .select_related("author")
        .prefetch_related("tags")
        .annotate(comments_count=Count("comments", distinct=True))
        .order_by("-published_at", "-created_at")
    )
    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    context = {
        "tag": tag,
        "page_obj": page_obj,
        "articles": page_obj.object_list,
        **_sidebar_context(),
    }
    return render(request, "blog/tag_detail.html", context)


def author_profile(request, username):
    author = get_object_or_404(User, username=username)
    published_qs = (
        Article.published.filter(author=author)
        .select_related("author")
        .prefetch_related("tags")
        .annotate(comments_count=Count("comments", distinct=True))
        .order_by("-published_at", "-created_at")
    )
    paginator = Paginator(published_qs, 10)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    drafts = []
    if request.user.is_authenticated and request.user == author:
        drafts = Article.objects.filter(author=author, status=Article.Status.DRAFT).order_by(
            "-updated_at"
        )

    context = {
        "profile_user": author,
        "page_obj": page_obj,
        "articles": page_obj.object_list,
        "drafts": drafts,
        **_sidebar_context(),
    }
    return render(request, "blog/author_profile.html", context)


def article_detail(request, slug):
    queryset = Article.objects.select_related("author").prefetch_related("tags")
    if request.user.is_authenticated:
        queryset = queryset.filter(
            Q(status=Article.Status.PUBLISHED) | Q(author=request.user)
        )
    else:
        queryset = queryset.filter(status=Article.Status.PUBLISHED)

    article = get_object_or_404(queryset, slug=slug)
    comments = article.comments.select_related("author").all()
    comment_form = CommentForm()

    context = {
        "article": article,
        "comments": comments,
        "comment_form": comment_form,
        **_sidebar_context(),
    }
    return render(request, "blog/article_detail.html", context)


@login_required
def article_create(request):
    if request.method == "POST":
        form = ArticleForm(request.POST)
        if form.is_valid():
            article = form.save(commit=False)
            article.author = request.user
            article.save()
            form._save_tags(article)
            messages.success(request, "Article saved successfully.")
            return redirect("blog:article_detail", slug=article.slug)
    else:
        form = ArticleForm(initial={"status": Article.Status.PUBLISHED})

    return render(request, "blog/article_form.html", {"form": form, "is_edit": False})


@login_required
def article_edit(request, slug):
    article = get_object_or_404(Article, slug=slug, author=request.user)
    if request.method == "POST":
        form = ArticleForm(request.POST, instance=article)
        if form.is_valid():
            updated_article = form.save()
            messages.success(request, "Article updated successfully.")
            return redirect("blog:article_detail", slug=updated_article.slug)
    else:
        form = ArticleForm(instance=article)

    return render(
        request,
        "blog/article_form.html",
        {"form": form, "article": article, "is_edit": True},
    )


@login_required
def article_delete(request, slug):
    article = get_object_or_404(Article, slug=slug, author=request.user)
    if request.method == "POST":
        article.delete()
        messages.success(request, "Article deleted.")
        return redirect("blog:author_profile", username=request.user.username)

    return render(request, "blog/article_confirm_delete.html", {"article": article})


@login_required
@require_POST
def article_clap(request, slug):
    article = get_object_or_404(Article, slug=slug, status=Article.Status.PUBLISHED)
    Clap.objects.create(article=article, user=request.user)
    Article.objects.filter(pk=article.pk).update(claps_count=F("claps_count") + 1)
    article.refresh_from_db()

    if request.headers.get("HX-Request") == "true":
        return render(request, "blog/partials/clap_button.html", {"article": article})

    return redirect("blog:article_detail", slug=article.slug)


@login_required
@require_POST
def article_comment(request, slug):
    article = get_object_or_404(Article, slug=slug, status=Article.Status.PUBLISHED)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.article = article
        comment.author = request.user
        comment.save()
        form = CommentForm()

    comments = article.comments.select_related("author").all()
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "blog/partials/comments_section.html",
            {"article": article, "comments": comments, "comment_form": form},
        )

    return redirect("blog:article_detail", slug=article.slug)


def register_view(request):
    if request.user.is_authenticated:
        return redirect("blog:home")

    next_url = request.GET.get("next") or request.POST.get("next") or ""
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to Inkwell, {user.username}!")
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}
            ):
                return redirect(next_url)
            return redirect("blog:home")
    else:
        form = UserRegistrationForm()

    return render(request, "blog/auth/register.html", {"form": form, "next": next_url})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("blog:home")

    next_url = request.GET.get("next") or request.POST.get("next") or ""
    if request.method == "POST":
        form = BootstrapAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, "Signed in successfully.")
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}
            ):
                return redirect(next_url)
            return redirect("blog:home")
    else:
        form = BootstrapAuthenticationForm(request)

    return render(request, "blog/auth/login.html", {"form": form, "next": next_url})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "You have been signed out.")
    return redirect("blog:home")
