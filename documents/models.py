from django.conf import settings
from django.db import models


class Document(models.Model):
    class Status(models.TextChoices):
        DRAFT = "Draft", "Draft"
        FOR_REVIEW = "For Review", "For Review"
        FINALIZED = "Finalized", "Finalized"
        ARCHIVED = "Archived", "Archived"

    filename = models.CharField(max_length=255, blank=True)
    date_received = models.DateField(null=True, blank=True)
    date_of_document = models.DateField(null=True, blank=True)
    sender = models.CharField(max_length=255, blank=True)
    originating_office = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=500, blank=True)
    document_type = models.CharField(max_length=100, blank=True)
    important_details = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    keywords = models.JSONField(default=list, blank=True)
    ocr_text = models.TextField(blank=True)
    file = models.FileField(upload_to="documents/%Y/%m/", blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="documents")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.subject or self.filename or f"Document {self.pk}"
