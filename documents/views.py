import csv
from datetime import date, timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import DocumentReviewForm, DocumentUploadForm, PrototypeUserCreationForm
from .models import Document
from .services import extract_fields, extract_ocr, parse_date


def user_document(request, pk):
    return get_object_or_404(Document, pk=pk, created_by=request.user)


def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            return render(request, "403.html", status=403)
        return view_func(request, *args, **kwargs)
    return wrapped


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
        document.date_of_document = parse_date(fields.get("date_of_document")) or document.date_of_document
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
        document = form.save(commit=False)
        if request.POST.get("action") == "finalize":
            document.status = Document.Status.FINALIZED
            message = "Document finalized and added to the official records."
        else:
            document.status = Document.Status.FOR_REVIEW
            message = "Document draft saved for review."
        document.save()
        messages.success(request, message)
        return redirect("review-document", pk=document.pk)
    return render(request, "documents/review.html", {
        "document": document,
        "form": form,
        "is_pdf": document.filename.lower().endswith(".pdf"),
    })


@login_required
def records(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    document_type = request.GET.get("document_type", "").strip()
    date_received = request.GET.get("date_received", "").strip()
    documents = Document.objects.filter(created_by=request.user)
    if query:
        documents = documents.filter(Q(sender__icontains=query) | Q(subject__icontains=query) | Q(originating_office__icontains=query) | Q(document_type__icontains=query) | Q(keywords__icontains=query))
    if status:
        documents = documents.filter(status=status)
    if document_type:
        documents = documents.filter(document_type__icontains=document_type)
    if date_received:
        documents = documents.filter(date_received=date_received)
    return render(request, "documents/records.html", {
        "documents": documents,
        "query": query,
        "status": status,
        "document_type": document_type,
        "date_received": date_received,
        "status_choices": Document.Status.choices,
    })


@login_required
def document_detail(request, pk):
    document = user_document(request, pk)
    return render(request, "documents/detail.html", {
        "document": document,
        "is_pdf": document.filename.lower().endswith(".pdf"),
    })


@login_required
def reports(request):
    today = date.today()
    start_date = parse_date(request.GET.get("start_date", "")) or (today - timedelta(days=6))
    end_date = parse_date(request.GET.get("end_date", "")) or today
    documents = Document.objects.filter(created_by=request.user, date_received__range=(start_date, end_date))
    if request.GET.get("format") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="incoming-correspondence-{start_date}-{end_date}.csv"'
        writer = csv.writer(response)
        writer.writerow(["Record ID", "Date Received", "Sender", "Subject", "Document Type", "Status"])
        for document in documents:
            writer.writerow([document.pk, document.date_received, document.sender, document.subject, document.document_type, document.status])
        return response
    return render(request, "reports.html", {
        "documents": documents,
        "start_date": start_date,
        "end_date": end_date,
        "total_documents": documents.count(),
    })


@admin_required
def user_management(request):
    user_model = get_user_model()
    form = PrototypeUserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "User account created.")
        return redirect("user-management")
    if request.method == "POST" and request.POST.get("action") == "toggle":
        target = get_object_or_404(user_model, pk=request.POST.get("user_id"))
        if target != request.user and not target.is_superuser:
            target.is_active = not target.is_active
            target.save(update_fields=["is_active"])
            messages.success(request, "User status updated.")
        return redirect("user-management")
    return render(request, "user_management.html", {"users": user_model.objects.order_by("username"), "form": form})


def permission_denied(request, exception=None):
    return render(request, "403.html", status=403)


def page_not_found(request, exception=None):
    return render(request, "404.html", status=404)


def server_error(request):
    return render(request, "500.html", status=500)
