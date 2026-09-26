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

        configured_tesseract = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if Path(configured_tesseract).exists():
            pytesseract.pytesseract.tesseract_cmd = configured_tesseract

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
    """Deterministic extraction for common office documents; never presented as real AI."""
    lines = [re.sub(r"\s+", " ", line.strip()) for line in ocr_text.splitlines() if line.strip()]
    lower_text = " ".join(lines).lower()
    date_pattern = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"

    def labelled(label_names):
        labels = "|".join(re.escape(label) for label in label_names)
        pattern = rf"^(?:{labels})\s*[:\-]\s*(.+)$"
        return next((re.match(pattern, line, flags=re.I).group(1).strip() for line in lines if re.match(pattern, line, flags=re.I)), "")

    document_date = next((match.group(0) for line in lines if (match := re.search(date_pattern, line, flags=re.I))), "")
    sender = labelled(("from", "sender", "prepared by", "issued by"))
    originating_office = labelled(("originating office", "office", "department", "agency"))
    subject = labelled(("subject", "re", "regarding"))

    date_index = next((index for index, line in enumerate(lines) if re.search(date_pattern, line, flags=re.I)), -1)
    salutation_index = next((index for index, line in enumerate(lines) if re.match(r"^(dear|to whom it may concern)", line, flags=re.I)), -1)
    header_end = salutation_index if salutation_index >= 0 else min(len(lines), date_index + 6 if date_index >= 0 else 8)
    header_lines = lines[date_index + 1:header_end] if date_index >= 0 else lines[:header_end]

    if not sender:
        sender = next((line for line in header_lines if _looks_like_person_name(line) and "office" not in line.lower()), "")
    if not originating_office:
        originating_office = next((line for line in header_lines if _looks_like_organization(line)), "")

    document_type = _detect_document_type(lower_text)
    body_lines = _body_lines(lines, salutation_index, lower_text)
    sentences = _sentences(body_lines)
    if not subject:
        subject = _infer_subject(document_type, lower_text, sentences)
    detail_sentences = [sentence for sentence in sentences if _is_detail(sentence)]
    important_details = " ".join(detail_sentences[:3] or sentences[:2])
    summary = _build_summary(document_type, sender, originating_office, subject, sentences)
    keywords = _build_keywords(lower_text, subject, originating_office, document_type)

    return {
        "date_received": "",
        "date_of_document": document_date,
        "sender": sender,
        "originating_office": originating_office,
        "subject": subject,
        "document_type": document_type,
        "important_details": important_details,
        "summary": summary,
        "keywords": keywords,
    }


def _looks_like_person_name(line):
    words = re.findall(r"[A-Za-z][A-Za-z.'-]*", line)
    if not 2 <= len(words) <= 8 or any(word.lower() in {"dear", "subject", "date", "notice", "memorandum"} for word in words):
        return False
    return sum(word.isupper() or word.istitle() for word in words) >= max(2, len(words) - 1)


def _looks_like_organization(line):
    organization_words = ("office", "department", "university", "agency", "municipal", "provincial", "school", "college", "barangay")
    return len(line.split()) <= 12 and any(word in line.lower() for word in organization_words)


def _detect_document_type(text):
    if re.search(r"\bmemorandum\b|\bmemoranda\b|\bmemo\b", text):
        return "Memorandum"
    if re.search(r"\bnotice\b|\bannouncement\b", text):
        return "Notice"
    if re.search(r"\brequest\b|\brequesting\b|\bkindly grant\b", text):
        return "Request Letter"
    return "Letter"


def _body_lines(lines, salutation_index, text):
    start = salutation_index + 1 if salutation_index >= 0 else 0
    ignored = ("respectfully yours", "sincerely", "very truly yours", "noted by", "approved by")
    result = []
    for line in lines[start:]:
        if any(line.lower().startswith(prefix) for prefix in ignored):
            break
        if not re.match(r"^(greetings|dear\b)", line, flags=re.I):
            result.append(line)
    return result


def _sentences(lines):
    text = " ".join(lines)
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if len(sentence.strip()) > 20]


def _is_detail(sentence):
    detail_terms = ("meeting", "request", "submit", "deadline", "date", "time", "schedule", "confirm", "discuss", "required", "attached", "please", "propose", "project")
    return any(term in sentence.lower() for term in detail_terms)


def _infer_subject(document_type, text, sentences):
    if "meeting" in text and ("confirm" in text or "schedule" in text):
        return "Meeting confirmation"
    if document_type == "Request Letter":
        return "Request for assistance or action"
    if document_type == "Memorandum":
        return "Office memorandum"
    if document_type == "Notice":
        return "Official notice"
    return sentences[0][:160] if sentences else ""


def _build_summary(document_type, sender, office, subject, sentences):
    source = f" from {sender}" if sender else ""
    organization = f" of {office}" if office else ""
    opening = f"{document_type}{source}{organization} regarding {subject.lower() if subject else 'an office matter'}."
    detail = sentences[0] if sentences else "No readable body text was available for summarization."
    return f"{opening} {detail}"


def _build_keywords(text, subject, office, document_type):
    known_phrases = (
        "AI-powered document logging", "document management", "provincial agriculture office",
        "meeting", "project scope", "memorandum", "notice", "request", "deployment", "MOA",
    )
    keywords = [phrase for phrase in known_phrases if phrase.lower() in text]
    for phrase in (subject, office, document_type):
        if phrase and phrase not in keywords and len(phrase.split()) <= 8:
            keywords.append(phrase)
    stopwords = {"the", "and", "for", "with", "this", "that", "from", "your", "our", "you", "are", "will", "about", "please"}
    words = re.findall(r"[A-Za-z][A-Za-z-]{4,}", text)
    counts = {word.lower(): words.count(word) for word in words if word.lower() not in stopwords}
    for word, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        if word not in " ".join(keywords).lower() and len(keywords) < 8:
            keywords.append(word)
    return keywords[:8]


def _schema():
    return {
        "type": "object",
        "properties": {
            "date_received": {"type": "string"},
            "date_of_document": {"type": "string"},
            "sender": {"type": "string"},
            "originating_office": {"type": "string"},
            "subject": {"type": "string"},
            "document_type": {"type": "string"},
            "important_details": {"type": "string"},
            "summary": {"type": "string"},
            "keywords": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["date_received", "date_of_document", "sender", "originating_office", "subject", "document_type", "important_details", "summary", "keywords"],
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
