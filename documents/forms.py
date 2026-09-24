from pathlib import Path

from django import forms

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
        if uploaded_file.size > 10 * 1024 * 1024:
            raise forms.ValidationError("The maximum file size is 10 MB.")
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
