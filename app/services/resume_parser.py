"""
Единая точка парсинга резюме: HH (ссылка), PDF, MD.
Возвращает структуру с полем text_for_ai (всегда) и resume_ontology (для HH — полная, для PDF/MD — минимальная).
"""
import re

from app.services.hh_parser import HHResumeParserService
from app.services.pdf_parser import PDFResumeParser


# Ссылка на резюме hh.ru (типичные паттерны)
HH_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:hh\.ru|hh\.com)/resume/[a-f0-9-]+",
    re.IGNORECASE,
)


def _ontology_to_text(ontology: dict) -> str:
    """Собирает читаемый текст из онтологии HH для передачи в ИИ."""
    parts = []

    pi = ontology.get("personal_info") or {}
    if pi.get("full_name") or pi.get("name"):
        parts.append(f"ФИО: {pi.get('full_name') or pi.get('name')}")
    if pi.get("birth_date") or pi.get("age"):
        parts.append(f"Возраст/дата рождения: {pi.get('birth_date') or pi.get('age')}")
    if pi.get("gender"):
        parts.append(f"Пол: {pi.get('gender')}")
    if pi.get("relocation"):
        parts.append(f"Переезд: {pi.get('relocation')}")
    if pi.get("business_trip_readiness"):
        parts.append(f"Командировки: {pi.get('business_trip_readiness')}")

    pos = ontology.get("position") or {}
    if pos.get("title"):
        parts.append(f"\nЖелаемая должность: {pos['title']}")
    if pos.get("salary"):
        s = pos["salary"]
        if isinstance(s, dict) and s.get("amount"):
            parts.append(f"Зарплата: {s.get('amount')} {s.get('currency', '')}")
    if pos.get("employment"):
        parts.append(f"Занятость: {pos['employment']}")
    if pos.get("schedule"):
        parts.append(f"График: {pos['schedule']}")

    loc = ontology.get("location") or {}
    if loc.get("city"):
        parts.append(f"\nГород: {loc['city']}")
    if loc.get("citizenship"):
        parts.append(f"Гражданство: {loc['citizenship']}")

    exp = ontology.get("experience") or []
    if exp:
        parts.append("\n--- Опыт работы ---")
        for i, e in enumerate(exp):
            if isinstance(e, dict) and e.get("type") == "total":
                parts.append(f"Всего: {e.get('years', 0)} лет {e.get('months', 0)} мес.")
                continue
            if isinstance(e, dict):
                company = e.get("company") or "?"
                position = e.get("position") or "?"
                period = f"{e.get('start_date') or '?'} — {e.get('end_date') or 'н.в.'}"
                parts.append(f"{i + 1}. {position} в {company}. {period}")
                if e.get("description"):
                    parts.append(f"   {e['description'][:300]}")

    edu = ontology.get("education") or []
    if edu:
        parts.append("\n--- Образование ---")
        for e in edu:
            if isinstance(e, dict) and e.get("institution"):
                parts.append(f"- {e['institution']}: {e.get('specialization') or e.get('result') or ''} ({e.get('year') or ''})")

    skills = ontology.get("skills") or []
    if skills:
        names = []
        for s in skills:
            if isinstance(s, dict) and s.get("name"):
                names.append(s["name"])
        if names:
            parts.append("\n--- Навыки ---")
            parts.append(", ".join(names[:30]))

    lang = ontology.get("languages") or []
    if lang:
        parts.append("\n--- Языки ---")
        for l in lang:
            if isinstance(l, dict) and l.get("name"):
                parts.append(f"- {l['name']}: {l.get('level', '')}")

    add = ontology.get("additional_info") or {}
    if add.get("total_experience"):
        te = add["total_experience"]
        parts.append(f"\nОбщий опыт: {te.get('years', 0)} лет {te.get('months', 0)} мес.")
    if add.get("specializations"):
        parts.append(f"Специализации: {add['specializations']}")

    return "\n".join(parts).strip() if parts else ""


def parse_resume(source_type: str, source_value: str = "", file_content: bytes | None = None) -> dict:
    """
    Парсит резюме по типу источника.

    source_type: "url" | "pdf" | "md"
    source_value: для url — ссылка на HH; для pdf/md не используется.
    file_content: для pdf/md — содержимое файла (bytes для PDF, для MD можно передать .decode() и положить в ontology как text).

    Возвращает: {"resume_ontology": dict, "text_for_ai": str}
    """
    if source_type == "url":
        ontology = HHResumeParserService.parse_resume_by_url(source_value)
        text_for_ai = _ontology_to_text(ontology)
        return {"resume_ontology": ontology, "text_for_ai": text_for_ai or "Резюме по ссылке (данные не извлечены)."}

    if source_type == "pdf":
        if not file_content:
            raise ValueError("Для PDF нужен file_content")
        text = PDFResumeParser.extract_text(file_content)
        ontology = {"source": "pdf", "text_for_ai": text}
        return {"resume_ontology": ontology, "text_for_ai": text or "Текст из PDF не извлечён."}

    if source_type == "md":
        if not file_content:
            raise ValueError("Для MD нужен file_content")
        try:
            text = file_content.decode("utf-8")
        except UnicodeDecodeError:
            text = file_content.decode("utf-8", errors="replace")
        ontology = {"source": "md", "text_for_ai": text}
        return {"resume_ontology": ontology, "text_for_ai": text.strip() or "Файл пустой."}

    raise ValueError(f"Неизвестный тип источника: {source_type}")


def is_hh_resume_url(text: str) -> bool:
    """Проверяет, похоже ли сообщение на ссылку на резюме HH."""
    return bool(text and HH_URL_PATTERN.search(text.strip()))
