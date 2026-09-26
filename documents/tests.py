from django.test import SimpleTestCase
from unittest.mock import MagicMock, patch

from .services import _fallback_extraction, extract_fields


class DemoFallbackExtractionTests(SimpleTestCase):
    def test_formal_letter(self):
        result = _fallback_extraction(
            "September 24, 2026\nPAgRO RUBY ANN LAGAHIT\nProvincial Agriculture Office\n"
            "Dear Ma'am Lagahit:\nWe respectfully confirm our meeting on Monday, September 28, 2026, at 9:00 AM.\n"
            "Respectfully yours,"
        )
        self.assertEqual(result["document_type"], "Letter")
        self.assertEqual(result["originating_office"], "Provincial Agriculture Office")
        self.assertIn("meeting", result["summary"].lower())

    def test_labeled_request_letter(self):
        result = _fallback_extraction(
            "Date: September 24, 2026\nFrom: Maria Santos\nOffice: Municipal Agriculture Office\n"
            "Subject: Request for seed assistance\nDear Sir/Madam:\nWe request seed assistance for our farmer beneficiaries."
        )
        self.assertEqual(result["sender"], "Maria Santos")
        self.assertEqual(result["document_type"], "Request Letter")
        self.assertEqual(result["subject"], "Request for seed assistance")

    def test_memorandum(self):
        result = _fallback_extraction(
            "MEMORANDUM\nDate: September 24, 2026\nTo: All Personnel\nFrom: Office of the Director\n"
            "Subject: Staff meeting\nPlease attend the meeting on Friday at 2:00 PM."
        )
        self.assertEqual(result["document_type"], "Memorandum")
        self.assertEqual(result["subject"], "Staff meeting")

    @patch.dict("os.environ", {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "test-model"}, clear=False)
    @patch("google.genai.Client")
    def test_gemini_structured_response_is_normalized(self, client_class):
        client = client_class.return_value
        client.models.generate_content.return_value = MagicMock(text='{"sender":"Maria Santos","keywords":["request"]}')
        result, source, warning = extract_fields("A fabricated request letter")
        self.assertEqual(source, "GEMINI")
        self.assertIsNone(warning)
        self.assertEqual(result["sender"], "Maria Santos")
        self.assertEqual(result["keywords"], ["request"])
