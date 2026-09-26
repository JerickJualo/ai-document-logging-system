# Client Demonstration Checklist

## Before the meeting

1. Activate the virtual environment:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. Confirm Tesseract is available:

   ```powershell
   & 'C:\Program Files\Tesseract-OCR\tesseract.exe' --version
   ```

3. Keep the project in demo mode unless an approved cloud/local provider is configured:

   ```env
   AI_PROVIDER=demo
   ```

4. Start Django:

   ```powershell
   python manage.py runserver
   ```

5. Log in with a prepared Django user and use only fabricated or non-confidential documents.

## Demonstration flow

Login → Dashboard → New Document → Upload → Process → Review OCR and extracted fields → Correct fields → Save Draft or Finalize → Records → Search → Details → Reports → CSV.

## Important explanation

This is a working demonstration prototype. OCR and DEMO/FALLBACK extraction may contain errors. Office personnel must verify the fields before finalization. The Brother scanner is a future input device; this prototype uses uploaded digital files.
