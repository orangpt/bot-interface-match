import json
import re
from pathlib import Path

import httpx
from aiogram import Router, types
from asgiref.sync import sync_to_async
from django.conf import settings
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted
from reportlab.lib.styles import getSampleStyleSheet

from app.CandidateDescriptionService import CandidateDescriptionService
from app.CandidateYouMapService import CandidateYouMapService
from app.CareerPathService import CareerPathService
from app.HHMarketService import HHMarketService
from app.hidden_skills_service import HiddenSkillsService
from app.service import ClientService, HHResumeParserService

router = Router()

URL_REGEX = re.compile(r'https?://[^\s]+')

hh_parser_service = HHResumeParserService()
candidate_description_service = CandidateDescriptionService()
hh_market_service = HHMarketService()


ONTOLOGY_PATH = Path(__file__).resolve().parent.parent / "ontology_generated.json"
hidden_skills_service = HiddenSkillsService(ONTOLOGY_PATH)
youmap_service = CandidateYouMapService(
    ontology_file=ONTOLOGY_PATH,
    openai_api_key="REMOVED"
)

career_path_service = CareerPathService(
    hh_market_service=hh_market_service,
    youmap_service=youmap_service
)

# === Шрифты ===
try:
    font_path = Path(__file__).resolve().parent.parent / "fonts" / "DejaVuSans.ttf"
    if not font_path.exists():
        raise FileNotFoundError("DejaVuSans.ttf не найден")
    pdfmetrics.registerFont(TTFont("DejaVuSans", str(font_path)))
    addMapping("DejaVuSans", 0, 0, "DejaVuSans")
    default_font = "DejaVuSans"
except Exception as e:
    print(f"[⚠️] Не удалось подключить DejaVuSans: {e}")
    try:
        arial_path = Path("C:/Windows/Fonts/arial.ttf")
        pdfmetrics.registerFont(TTFont("Arial", str(arial_path)))
        addMapping("Arial", 0, 0, "Arial")
        default_font = "Arial"
    except Exception as e2:
        print(f"[‼️] Не удалось подключить Arial: {e2}")
        default_font = "Helvetica"

# === Стили ===
styles = getSampleStyleSheet()
for style in styles.byName.values():
    style.fontName = default_font


def split_long_text(text, max_length=100):
    """Разбивает длинные строки на несколько строк, чтобы ReportLab не глючил"""
    parts = []
    current = ""
    for word in str(text).split(","):
        word = word.strip()
        if len(current) + len(word) + 2 > max_length:
            parts.append(current)
            current = word
        else:
            current += (", " if current else "") + word
    if current:
        parts.append(current)
    return "\n".join(parts)


@router.message()
async def handle_resume_link(message: types.Message):
    """Обработка ссылки на резюме — генерирует PDF с YouMap."""
    text = message.text

    if not text.startswith("http"):
        await message.answer("⚠️ Отправь, пожалуйста, ссылку на резюме.")
        return

    try:
        telegram_id = message.from_user.id
        link = text

        # Привязываем резюме
        await sync_to_async(ClientService.link_client_hh_tg)(telegram_id, link)
        await message.answer("✅ Ссылка получена! Формирую карту навыков...")

        # Парсим и получаем рекомендации
        resume_dict = hh_parser_service.parse_resume_by_url(link)


        candidate_description = candidate_description_service.build_candidate_description(resume_dict)
        hidden_skills_searched = hh_market_service.analyze_candidate(candidate_description)

        # === Генерация онтологии кандидата ===
        candidate_ontology = youmap_service.generate_candidate_ontology(resume_dict)

        # Сохраняем временно для отладки (не обязательно)
        with open("candidate_ontology.json", "w", encoding="utf-8") as f:
            json.dump(candidate_ontology, f, ensure_ascii=False, indent=2)

        # Теперь подменяем онтологию в сервисе на индивидуальную
        youmap_service.relations = candidate_ontology["relations"]
        youmap_service.known_terms = set(candidate_ontology["skills"])

        recommendations = youmap_service.generate_recommendations(resume_dict)

        growth_plan = career_path_service.generate_growth_plan(
            candidate_description=candidate_description,
            target_vacancies=hh_market_service.get_target_vacancies(candidate_description),
            roi_map=hidden_skills_searched  # скрытые навыки можно использовать как приоритет
        )

        known_skills = recommendations.get("known_skills", [])
        hidden_skills = hidden_skills_searched
        bridges = recommendations.get("bridges", [])
        recommend_texts = growth_plan
        raw_clusters = recommendations.get("clusters", [])

        # --- Приведение кластеров ---
        clusters = []
        for c in raw_clusters:
            if isinstance(c, dict):
                clusters.append(c)
            elif isinstance(c, (set, list, tuple)):
                clusters.append({"name": "Cluster", "skills": list(c)})
            else:
                clusters.append({"name": "Cluster", "skills": [str(c)]})

        # === Генерация PDF ===
        pdf_filename = f"youmap_{telegram_id}.pdf"
        doc = SimpleDocTemplate(pdf_filename, pagesize=A4)
        story = []

        story.append(Paragraph("<b>🧭 You-Map кандидата</b>", styles["Title"]))
        story.append(Spacer(1, 12))

        # Кластеры
        for cluster in clusters:
            cluster_name = cluster.get("name", "Cluster")
            cluster_skills = ", ".join(cluster.get("skills", []))
            formatted = split_long_text(cluster_skills)

            story.append(Paragraph(f"<b>{cluster_name}</b>", styles["Heading3"]))
            story.append(Preformatted(formatted, styles["Normal"]))
            story.append(Spacer(1, 8))

        def add_section(title, items):
            story.append(Paragraph(f"<b>{title}</b>", styles["Heading2"]))
            story.append(Spacer(1, 6))
            if not items:
                story.append(Paragraph("—", styles["Normal"]))
            else:
                for item in items:
                    story.append(Paragraph(f"• {item}", styles["Normal"]))
            story.append(Spacer(1, 12))

        # Разделы
        add_section("Известные навыки", known_skills)
        add_section("Скрытые навыки", hidden_skills)
        add_section("Мосты между навыками", bridges)
        add_section("Рекомендации для развития", recommend_texts)

        doc.build(story)

        # Отправляем PDF пользователю
        await message.answer_document(
            document=types.FSInputFile(pdf_filename),
            caption="📄 Ваша персональная You-Map готова!"
        )

    except httpx.RequestError:
        await message.answer("❌ Ошибка подключения к сервису.")
    except httpx.HTTPStatusError as e:
        await message.answer(f"❌ Ошибка от сервера: {e.response.status_code}")
    except Exception as e:
        await message.answer(f"⚠️ Произошла ошибка: {e}")


def register_handlers(dp):
    dp.include_router(router)
