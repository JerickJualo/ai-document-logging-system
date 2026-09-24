from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "subject", "sender", "status", "created_by", "created_at")
    list_filter = ("status", "document_type", "created_at")
    search_fields = ("subject", "sender", "originating_office", "filename")
