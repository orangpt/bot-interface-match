"""Извлечение текста из PDF-файлов резюме."""
from io import BytesIO

from pypdf import PdfReader


class PDFResumeParser:
    """Извлечение текста из PDF для передачи в ИИ."""

    @staticmethod
    def extract_text(content: bytes) -> str:
        """Извлекает текст из PDF. content — байты файла."""
        reader = PdfReader(BytesIO(content))
        parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
        return "\n".join(parts).strip() if parts else ""
