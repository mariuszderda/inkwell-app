from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    path("", views.home, name="home"),
    path("search/", views.home, name="search"),
    path("tag/<slug:slug>/", views.tag_detail, name="tag_detail"),
    path("author/<str:username>/", views.author_profile, name="author_profile"),
    path("write/", views.article_create, name="article_create"),
    path("article/<slug:slug>/", views.article_detail, name="article_detail"),
    path("article/<slug:slug>/edit/", views.article_edit, name="article_edit"),
    path("article/<slug:slug>/delete/", views.article_delete, name="article_delete"),
    path("article/<slug:slug>/clap/", views.article_clap, name="article_clap"),
    path("article/<slug:slug>/comment/", views.article_comment, name="article_comment"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
]
