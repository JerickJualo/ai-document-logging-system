from datetime import date

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Document


class WorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="personnel", password="test-password-123")
        self.admin = User.objects.create_superuser(username="admin", password="test-password-123", email="admin@example.com")

    def test_login_protects_dashboard(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_valid_upload_creates_document(self):
        self.client.login(username="personnel", password="test-password-123")
        upload = SimpleUploadedFile("letter.pdf", b"%PDF-1.7 demo", content_type="application/pdf")
        response = self.client.post(reverse("upload-document"), {"file": upload})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Document.objects.count(), 1)

    def test_report_csv_contains_records(self):
        document = Document.objects.create(created_by=self.user, filename="letter.pdf", date_received=date.today(), subject="Test subject")
        self.client.login(username="personnel", password="test-password-123")
        response = self.client.get(reverse("reports"), {"start_date": date.today(), "end_date": date.today(), "format": "csv"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test subject", response.content)

    def test_non_admin_cannot_manage_users(self):
        self.client.login(username="personnel", password="test-password-123")
        self.assertEqual(self.client.get(reverse("user-management")).status_code, 403)

    def test_admin_can_manage_users(self):
        self.client.login(username="admin", password="test-password-123")
        response = self.client.get(reverse("user-management"))
        self.assertEqual(response.status_code, 200)

    def test_finalize_record(self):
        document = Document.objects.create(created_by=self.user, filename="letter.pdf", status=Document.Status.FOR_REVIEW)
        self.client.login(username="personnel", password="test-password-123")
        response = self.client.post(reverse("review-document", args=[document.pk]), {
            "date_received": date.today().isoformat(), "date_of_document": "", "sender": "Sender",
            "originating_office": "Office", "subject": "Subject", "document_type": "Letter",
            "important_details": "Details", "summary": "Summary", "keywords_text": "test, letter",
            "action": "finalize",
        })
        self.assertEqual(response.status_code, 302)
        document.refresh_from_db()
        self.assertEqual(document.status, Document.Status.FINALIZED)

    def test_document_created_by_one_user_is_visible_to_another_user(self):
        document = Document.objects.create(
            created_by=self.admin,
            filename="shared-letter.pdf",
            subject="Shared office record",
            status=Document.Status.FINALIZED,
        )
        self.client.login(username="personnel", password="test-password-123")
        self.assertContains(self.client.get(reverse("records")), "Shared office record")
        self.assertContains(self.client.get(reverse("dashboard")), "Shared office record")
        self.assertEqual(self.client.get(reverse("document-detail", args=[document.pk])).status_code, 200)
