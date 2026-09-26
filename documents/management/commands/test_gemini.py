import os

from django.core.management.base import BaseCommand, CommandError

from documents.services import _gemini_extraction


class Command(BaseCommand):
    help = "Send a safe fabricated test sentence to Gemini and report whether the configured provider responds."

    def handle(self, *args, **options):
        api_key = os.getenv("GEMINI_API_KEY", "")
        model = os.getenv("GEMINI_MODEL", "")
        if not api_key or not model:
            raise CommandError("Set GEMINI_API_KEY and GEMINI_MODEL in .env first.")
        try:
            result = _gemini_extraction(
                "Date: September 24, 2026. From: Maria Santos. Office: Municipal Agriculture Office. "
                "Subject: Request for seed assistance. The office requests seed assistance for farmer beneficiaries.",
                api_key,
                model,
            )
        except Exception as exc:
            raise CommandError(f"Gemini test failed: {exc}") from exc
        self.stdout.write(self.style.SUCCESS("Gemini connection succeeded."))
        self.stdout.write(f"Document type: {result['document_type']}")
        self.stdout.write(f"Subject: {result['subject']}")
