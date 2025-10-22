import re
import httpx
from aiogram import Router, types
from asgiref.sync import sync_to_async
from django.conf import settings

from app.service import ClientService

router = Router()

URL_REGEX = re.compile(r'https?://[^\s]+')


@router.message()
async def handle_resume_link(message: types.Message):
    """Если пользователь отправил ссылку — шлём её в твой сервис."""
    text = message.text.strip()

    if not URL_REGEX.match(text):
        await message.answer("⚠️ Отправь, пожалуйста, ссылку на резюме.")
        return


    try:
        telegram_id = message.from_user.id
        link = text
        # Обернули синхронный метод в async
        await sync_to_async(ClientService.link_client_hh_tg)(telegram_id, link)
        await message.answer("✅ Ссылка успешно отправлена в сервис!")
    except httpx.RequestError:
        await message.answer("❌ Ошибка подключения к сервису.")
    except httpx.HTTPStatusError as e:
        await message.answer(f"❌ Ошибка от сервера: {e.response.status_code}")

def register_handlers(dp):
    dp.include_router(router)
