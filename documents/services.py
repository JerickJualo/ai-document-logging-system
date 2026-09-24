import io
import json
import os
import re
from datetime import date, datetime
from pathlib import Path

from PIL import Image, ImageOps


def _preprocess(image):
    image = image.convert("L")
    image = ImageOps.autocontrast(image)
    if image.width < 1600:
        scale = 1600 / image.width
        image = image.resize((1600, max(1, int(image.height * scale))))
    return image


def extract_ocr(uploaded_file):
    """Return OCR text and a human-readable processing warning, if any."""
    try:
        import pytesseract
        from django.core.files.storage import default_storage

        with default_storage.open(uploaded_file.name, "rb") as source:
            content = source.read()
        extension = Path(uploaded_file.name).suffix.lower()
        images = []
        if extension == ".pdf":
            import fitz

            pdf = fitz.open(stream=content, filetype="pdf")
            for page in pdf:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                images.append(Image.open(io.BytesIO(pixmap.tobytes("png"))).copy())
            pdf.close()
        else:
            images.append(Image.open(io.BytesIO(content)).copy())

        text_parts = [pytesseract.image_to_string(_preprocess(image)).strip() for image in images]
        text = "\n\n".join(part for part in text_parts if part)
        return text, None if text else "OCR completed but no readable text was detected."
    except Exception as exc:
        return "", f"OCR could not be completed: {exc}"


def _fallback_extraction(ocr_text):
    """Simple deterministic demo provider; never presented as real AI."""
    lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]
    subject = next((line for line in lines if "subject:" in line.lower()), "")
    sender = next((line for line in lines if "from:" in line.lower() or "sender:" in line.lower()), "")
    return {
        "date_received": "",
        "sender": re.sub(r"^(from|sender):\s*", "", sender, flags=re.I),
        "originating_office": "",
        "subject": re.sub(r"^subject:\s*", "", subject, flags=re.I),
        "document_type": "",
        "important_details": "",
        "summary": " ".join(lines[:3]),
        "keywords": [],
    }


def _schema():
    return {
        "type": "object",
        "properties": {
            "date_received": {"type": "string"},
            "sender": {"type": "string"},
            "originating_office": {"type": "string"},
            "subject": {"type": "string"},
            "document_type": {"type": "string"},
            "important_details": {"type": "string"},
            "summary": {"type": "string"},
            "keywords": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["date_received", "sender", "originating_office", "subject", "document_type", "important_details", "summary", "keywords"],
        "additionalProperties": False,
    }


def extract_fields(ocr_text):
    provider = os.getenv("AI_PROVIDER", "demo").lower()
    api_key = os.getenv("AI_API_KEY", "")
    model = os.getenv("AI_MODEL", "")
    if provider != "openai" or not api_key or not model:
        return _fallback_extraction(ocr_text), "DEMO/FALLBACK", "AI provider is not configured; demo extraction was used."
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": "Extract office correspondence fields from OCR text. Do not invent information; use empty strings when unknown."},
                {"role": "user", "content": ocr_text},
            ],
            text={"format": {"type": "json_schema", "name": "office_correspondence", "strict": True, "schema": _schema()}},
        )
        data = json.loads(response.output_text)
        if not isinstance(data.get("keywords"), list):
            raise ValueError("AI returned invalid keywords")
        return data, "OPENAI", None
    except Exception as exc:
        return _fallback_extraction(ocr_text), "DEMO/FALLBACK", f"AI processing failed; demo extraction was used ({exc})."


def parse_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None
