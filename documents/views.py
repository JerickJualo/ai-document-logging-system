from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import DocumentReviewForm, DocumentUploadForm
from .models import Document
from .services import extract_fields, extract_ocr, parse_date


def user_document(request, pk):
    return get_object_or_404(Document, pk=pk, created_by=request.user)


@login_required
def dashboard(request):
    documents = Document.objects.filter(created_by=request.user)
    context = {
        "total_documents": documents.count(),
        "for_review": documents.filter(status=Document.Status.FOR_REVIEW).count(),
        "finalized": documents.filter(status=Document.Status.FINALIZED).count(),
        "received_today": documents.filter(created_at__date=date.today()).count(),
        "recent_documents": documents[:5],
    }
    return render(request, "dashboard.html", context)


@login_required
def upload_document(request):
    form = DocumentUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        document = form.save(commit=False)
        document.filename = document.file.name
        document.created_by = request.user
        document.save()
        messages.success(request, "File uploaded. It is ready for processing.")
        return redirect("process-document", pk=document.pk)
    return render(request, "documents/upload.html", {"form": form})


@login_required
def process_document(request, pk):
    document = user_document(request, pk)
    if request.method == "POST":
        ocr_text, ocr_warning = extract_ocr(document.file)
        fields, source, ai_warning = extract_fields(ocr_text)
        document.ocr_text = ocr_text
        document.date_received = parse_date(fields.get("date_received")) or document.date_received or date.today()
        for field in ("sender", "originating_office", "subject", "document_type", "important_details", "summary"):
            setattr(document, field, fields.get(field, ""))
        document.keywords = fields.get("keywords", [])
        document.status = Document.Status.FOR_REVIEW
        document.save()
        if ocr_warning:
            messages.warning(request, ocr_warning)
        if ai_warning:
            messages.info(request, f"{source}: {ai_warning}")
        return redirect("review-document", pk=document.pk)
    return render(request, "documents/process.html", {"document": document})


@login_required
def review_document(request, pk):
    document = user_document(request, pk)
    form = DocumentReviewForm(request.POST or None, instance=document)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Document draft saved for review.")
        return redirect("review-document", pk=document.pk)
    return render(request, "documents/review.html", {
        "document": document,
        "form": form,
        "is_pdf": document.filename.lower().endswith(".pdf"),
    })


@login_required
def records(request):
    query = request.GET.get("q", "").strip()
    documents = Document.objects.filter(created_by=request.user)
    if query:
        documents = documents.filter(Q(sender__icontains=query) | Q(subject__icontains=query) | Q(originating_office__icontains=query) | Q(document_type__icontains=query))
    return render(request, "documents/records.html", {"documents": documents, "query": query})
