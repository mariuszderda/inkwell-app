from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Article, Comment, Tag


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "you@example.com"}),
    )
    first_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Jane"}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Doe"}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class BootstrapAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class ArticleForm(forms.ModelForm):
    tags_input = forms.CharField(
        required=False,
        label="Tags",
        help_text="Comma-separated tags (e.g. python, django, kubernetes)",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "python, django, kubernetes",
            }
        ),
    )

    class Meta:
        model = Article
        fields = ("title", "body", "status")
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "Article title...",
                }
            ),
            "body": forms.Textarea(
                attrs={
                    "class": "form-control font-monospace",
                    "rows": 14,
                    "placeholder": "Write your story in Markdown...",
                }
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            existing_tags = ", ".join(self.instance.tags.values_list("name", flat=True))
            self.fields["tags_input"].initial = existing_tags

    def save(self, commit=True):
        article = super().save(commit=commit)
        if commit:
            self._save_tags(article)
        return article

    def _save_tags(self, article: Article):
        raw_tags = self.cleaned_data.get("tags_input", "")
        tag_names = [t.strip().lower() for t in raw_tags.split(",") if t.strip()]
        tag_objs = []
        for name in dict.fromkeys(tag_names):
            tag_obj, _ = Tag.objects.get_or_create(name=name[:64])
            tag_objs.append(tag_obj)
        article.tags.set(tag_objs)


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("body",)
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "What are your thoughts?",
                }
            ),
        }
        labels = {
            "body": "",
        }
