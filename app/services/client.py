"""
Обработка резюме пользователя: парсинг (HH/PDF/MD) → ИИ-анализ → сохранение в БД.
"""
import json
import os
from datetime import datetime

from django.conf import settings

from app.models import Client
from app.services.ai_service import get_analysis
from app.services.resume_parser import parse_resume

# Для обратной совместимости: старый метод link_client_hh_tg оставлен и делегирует в process_resume.


def process_resume(
    telegram_id: int,
    source_type: str,
    source_value: str = "",
    file_content: bytes | None = None,
) -> tuple[Client, str]:
    """
    Парсит резюме, запрашивает у ИИ рекомендации и скрытые навыки, сохраняет в БД.

    source_type: "url" | "pdf" | "md"
    source_value: для url — ссылка на HH
    file_content: для pdf/md — байты файла

    Возвращает (Client, ответ_ИИ_текстом).
    """
    parsed = parse_resume(
        source_type=source_type,
        source_value=source_value,
        file_content=file_content,
    )
    text_for_ai = parsed["text_for_ai"]
    ontology = parsed["resume_ontology"]

    ai_response = get_analysis(text_for_ai)

    link = source_value if source_type == "url" else None
    client = Client(
        telegram_id=telegram_id,
        source_type=source_type,
        hh_resume_link=link,
        resume_content=text_for_ai[:15000] if text_for_ai else "",
        resume_ontology=ontology,
    )
    client.save()

    if getattr(settings, "DEBUG", False):
        _save_to_temp_file(ontology, text_for_ai)

    return client, ai_response


def link_client_hh_tg(telegram_id: int, link: str):
    """
    Обработка резюме по ссылке HH: парсинг, ИИ, сохранение.
    Оставлен для совместимости; возвращает (client, ai_response_text).
    """
    client, ai_response = process_resume(
        telegram_id=telegram_id,
        source_type="url",
        source_value=link,
    )
    return client, ai_response


def _save_to_temp_file(ontology: dict, text_for_ai: str) -> None:
    """При DEBUG сохраняет срез в temp_dp.json."""
    try:
        main_info = {
            "timestamp": datetime.now().isoformat(),
            "personal_info": ontology.get("personal_info", {}),
            "position": ontology.get("position", {}),
            "experience_count": len(ontology.get("experience", [])),
            "education_count": len(ontology.get("education", [])),
            "skills_count": len(ontology.get("skills", [])),
            "text_for_ai_preview": (text_for_ai or "")[:500],
        }
        temp_file = os.path.join(settings.BASE_DIR, "temp_dp.json")
        existing_data = []
        if os.path.exists(temp_file):
            try:
                with open(temp_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                if not isinstance(existing_data, list):
                    existing_data = []
            except (json.JSONDecodeError, FileNotFoundError):
                existing_data = []
        existing_data.append(main_info)
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка при сохранении в temp_dp.json: {e}")
