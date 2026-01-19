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
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import mm

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
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if not font_path.exists():
        raise FileNotFoundError("DejaVuSans.ttf не найден")
    pdfmetrics.registerFont(TTFont("DejaVuSans", str(font_path)))
    addMapping("DejaVuSans", 0, 0, "DejaVuSans")
    default_font = "DejaVuSans"
except Exception as e:
    print(f"[⚠️] Не удалось подключить DejaVuSans: {e}")
    try:
        arial_path = Path("C:\\Users\\Vladimir\\PycharmProjects\\bot-interface-match\\bot\\handlers\\fonts\\DejaVuSans"
                          ".ttf")
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

        # убираем всё до первой запятой
        if "," in candidate_description:
            candidate_description = candidate_description.split(",", 1)[1]

        known_skills = list({skill.strip() for skill in candidate_description.split(",")})

        hidden_skills = hidden_skills_searched
        bridges = recommendations.get("bridges", [])
        recommend_texts = growth_plan
        raw_clusters = recommendations.get("clusters", [])

        print(growth_plan)

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

        story.append(Paragraph("<b>You-Map кандидата</b>", styles["Title"]))
        story.append(Spacer(1, 12))

        story.append(Paragraph(
            "Данный отчёт создан на основе анализа 300 актуальных вакансий, отобранных по заданным фильтрам. "
            "Он поможет вам оптимизировать структуру и формулировки резюме, а также спланировать дальнейшие карьерные треки.",
            styles["Normal"]
        ))
        story.append(Spacer(1, 12))

        # # Кластеры
        # for cluster in clusters:
        #     cluster_name = cluster.get("name", "Cluster")
        #     cluster_skills = ", ".join(cluster.get("skills", []))
        #     formatted = split_long_text(cluster_skills)
        #
        #     story.append(Paragraph(f"<b>{cluster_name}</b>", styles["Heading3"]))
        #     story.append(Preformatted(formatted, styles["Normal"]))
        #     story.append(Spacer(1, 8))

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
        # === Скрытые навыки ===
        story.append(Paragraph("<b>Скрытые навыки</b>", styles["Heading2"]))
        story.append(Spacer(1, 6))

        story.append(Paragraph(
            "Ниже представлены скрытые навыки и рассчитанный процент потери охвата вакансий при их отсутствии в вашем резюме. "
            "Если вы действительно обладаете этими навыками, рекомендуется добавить их в резюме — это поможет значительно расширить вашу воронку вакансий.",
            styles["Normal"]
        ))
        story.append(Spacer(1, 12))

        if isinstance(hidden_skills, dict) and hidden_skills:
            data = [["Навык", "Процент пропущенных\nвакансий из-за скрытых навыков (%)"]]

            # сортируем по убыванию и фильтруем навыки меньше 1%
            filtered_skills = {
                skill: value for skill, value in hidden_skills.items()
                if round((value / 200) * 100, 1) >= 1
            }

            if filtered_skills:
                for skill, value in sorted(filtered_skills.items(), key=lambda x: x[1], reverse=True):
                    percent = round((value / 200) * 100, 1)
                    skill_par = Paragraph(split_long_text(skill, max_length=60), styles["Normal"])
                    value_par = Paragraph(f"{percent}%", styles["Normal"])
                    data.append([skill_par, value_par])

                table = Table(data, colWidths=[80 * mm, 80 * mm])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('FONTNAME', (0, 0), (-1, -1), default_font),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightyellow]),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ]))
                story.append(table)
            else:
                story.append(Paragraph("— Нет скрытых навыков выше 1%", styles["Normal"]))
        else:
            story.append(Paragraph("— Нет скрытых навыков", styles["Normal"]))
        story.append(Spacer(1, 12))
        # === Мосты между навыками ===
        story.append(Paragraph("<b>Мосты между навыками</b>", styles["Heading2"]))
        story.append(Spacer(1, 6))

        if bridges:
            data = [["Навык 1", "Навык 2"]]

            for bridge in bridges:
                if isinstance(bridge, (list, tuple)) and len(bridge) == 2:
                    left, right = bridge
                else:
                    left, right = str(bridge), "—"

                left_par = Paragraph(str(left), styles["Normal"])
                right_par = Paragraph(str(right), styles["Normal"])

                data.append([left_par, right_par])

            table = Table(data, colWidths=[90 * mm, 90 * mm])

            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('FONTNAME', (0, 0), (-1, -1), default_font),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightyellow]),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            story.append(table)
        else:
            story.append(Paragraph("— Мосты не найдены", styles["Normal"]))

        story.append(Spacer(1, 12))
        # === Карьерный рост по периодам ===
        # === Карьерный рост по периодам ===
        story.append(Paragraph("<b>Возможности карьерного роста</b>", styles["Heading2"]))
        story.append(Spacer(1, 6))

        story.append(Paragraph(
            "Ниже представлен рекомендуемый карьерный трек: указаны ключевые навыки, которые стоит освоить на каждом этапе, "
            "предполагаемая длительность периода и ориентировочная вилка заработной платы.",
            styles["Normal"]
        ))
        story.append(Spacer(1, 12))

        if isinstance(growth_plan, list) and growth_plan:
            data = [["Нужное время", "Позиция", "Навыки для изучения", "Вилка"]]

            for step in growth_plan:
                period = step.get("period", "—")
                position = step.get("position", "—")
                learn_skills = step.get("learn_skills", [])
                salary = str(step.get("salary", "")).strip()

                # === Обработка вилки ===
                salary_from, salary_to = None, None

                if "-" in salary:
                    parts = [p.strip() for p in salary.split("-")]
                    if len(parts) == 2:
                        salary_from, salary_to = parts

                def is_nan(value):
                    return not value or value.lower() in ("nan", "none", "null", "-")

                def clean_salary_value(val):
                    """Удаляет .0 и пробелы"""
                    if not val or is_nan(val):
                        return None
                    # если это число, округляем и преобразуем в строку без .0
                    try:
                        num = float(val)
                        if num.is_integer():
                            return str(int(num))
                        return str(round(num, 2))
                    except ValueError:
                        return val.strip()

                salary_from = clean_salary_value(salary_from)
                salary_to = clean_salary_value(salary_to)

                if not salary_from and not salary_to:
                    salary_clean = "нет информации"
                elif not salary_from:
                    salary_clean = f"{salary_to}"
                elif not salary_to:
                    salary_clean = f"{salary_from}"
                else:
                    salary_clean = f"{salary_from} - {salary_to}"

                # === Навыки ===
                if isinstance(learn_skills, list):
                    learn_skills = ", ".join([s for s in learn_skills if s])

                # === Обёртка для PDF ===
                period_par = Paragraph(str(period), styles["Normal"])
                position_par = Paragraph(split_long_text(position, max_length=60), styles["Normal"])
                skills_par = Paragraph(split_long_text(learn_skills or "—", max_length=80), styles["Normal"])
                salary_par = Paragraph(salary_clean, styles["Normal"])

                data.append([period_par, position_par, skills_par, salary_par])

            # Настройка таблицы
            table = Table(data, colWidths=[25 * mm, 50 * mm, 50 * mm, 35 * mm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('FONTNAME', (0, 0), (-1, -1), default_font),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('ALIGN', (1, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightyellow]),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))

            story.append(table)
        else:
            story.append(Paragraph("— Нет данных о карьерном росте", styles["Normal"]))

        story.append(Spacer(1, 12))

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
