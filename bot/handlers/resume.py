import logging
import re
import traceback
from pathlib import Path

from aiogram import F, Router, types
from asgiref.sync import sync_to_async

from app.services import process_resume
from app.services.resume_parser import is_hh_resume_url

router = Router()
logger = logging.getLogger(__name__)

ALLOWED_DOC_EXTENSIONS = {".pdf", ".md"}

USER_ERROR_MESSAGE = "Произошла ошибка. Попробуйте позже."

# Лимит длины сообщения в Telegram
MAX_MESSAGE_LENGTH = 4096


def _log_exception():
    """Печатает полный traceback в консоль."""
    logger.exception("Ошибка при обработке резюме")
    traceback.print_exc()


async def _set_result_message(status_msg: types.Message, text: str) -> None:
    """Редактирует сообщение статуса под результат; при длине > 4096 дополняет вторым сообщением."""
    if len(text) <= MAX_MESSAGE_LENGTH:
        await status_msg.edit_text(text)
        return
    await status_msg.edit_text(text[: MAX_MESSAGE_LENGTH - 4] + "\n\n…")
    rest = text[MAX_MESSAGE_LENGTH - 4 :]
    while rest:
        chunk = rest[:MAX_MESSAGE_LENGTH]
        rest = rest[MAX_MESSAGE_LENGTH:]
        await status_msg.reply(chunk)


@router.message(F.text, F.text.func(lambda t: t and is_hh_resume_url(t)))
async def handle_resume_link(message: types.Message):
    """Текст — ссылка на резюме HH.ru."""
    link = message.text.strip()
    status_msg = await message.reply("⏳ Парсю резюме и запрашиваю рекомендации ИИ…")
    try:
        client, ai_response = await sync_to_async(process_resume)(
            telegram_id=message.from_user.id,
            source_type="url",
            source_value=link,
        )
        await _set_result_message(status_msg, ai_response)
    except Exception:
        _log_exception()
        await status_msg.edit_text(USER_ERROR_MESSAGE)


@router.message(F.document)
async def handle_resume_document(message: types.Message):
    """Документ: PDF или .md."""
    doc = message.document
    if not doc.file_name:
        await message.reply("⚠️ Отправьте файл с именем (PDF или .md).")
        return
    ext = Path(doc.file_name).suffix.lower()
    if ext not in ALLOWED_DOC_EXTENSIONS:
        await message.reply(
            "⚠️ Поддерживаются только форматы: PDF и Markdown (.md)."
        )
        return

    status_msg = await message.reply("⏳ Скачиваю файл и анализирую резюме…")
    try:
        content = await message.bot.download(message.document)
        file_bytes = content.getvalue()

        source_type = "pdf" if ext == ".pdf" else "md"
        client, ai_response = await sync_to_async(process_resume)(
            telegram_id=message.from_user.id,
            source_type=source_type,
            file_content=file_bytes,
        )
        await _set_result_message(status_msg, ai_response)
    except Exception:
        _log_exception()
        await status_msg.edit_text(USER_ERROR_MESSAGE)


def register_handlers(dp):
    dp.include_router(router)
