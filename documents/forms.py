from pathlib import Path

from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Document


ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["file"]

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        extension = Path(uploaded_file.name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError("Upload a PDF, JPG, JPEG, or PNG file.")
        if uploaded_file.size == 0:
            raise forms.ValidationError("The uploaded file is empty.")
        if uploaded_file.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise forms.ValidationError(f"The maximum file size is {settings.MAX_UPLOAD_SIZE_MB} MB.")
        header = uploaded_file.read(12)
        uploaded_file.seek(0)
        signatures = {
            ".pdf": header.startswith(b"%PDF"),
            ".jpg": header.startswith(b"\xff\xd8\xff"),
            ".jpeg": header.startswith(b"\xff\xd8\xff"),
            ".png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        }
        if not signatures[extension]:
            raise forms.ValidationError("The file contents do not match its extension or the file is corrupted.")
        return uploaded_file


class DocumentReviewForm(forms.ModelForm):
    keywords_text = forms.CharField(required=False, label="Keywords", help_text="Separate keywords with commas.")

    class Meta:
        model = Document
        fields = [
            "date_received", "date_of_document", "sender", "originating_office",
            "subject", "document_type", "important_details", "summary",
        ]
        widgets = {
            "date_received": forms.DateInput(attrs={"type": "date"}),
            "date_of_document": forms.DateInput(attrs={"type": "date"}),
            "important_details": forms.Textarea(attrs={"rows": 3}),
            "summary": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["keywords_text"].initial = ", ".join(self.instance.keywords or [])

    def save(self, commit=True):
        document = super().save(commit=False)
        document.keywords = [item.strip() for item in self.cleaned_data["keywords_text"].split(",") if item.strip()]
        if commit:
            document.save()
        return document


class PrototypeUserCreationForm(UserCreationForm):
    role = forms.ChoiceField(choices=(("personnel", "Office Personnel"), ("administrator", "Administrator")))

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "role", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = self.cleaned_data["role"] == "administrator"
        if commit:
            user.save()
        return user
