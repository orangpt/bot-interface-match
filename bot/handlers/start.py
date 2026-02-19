from aiogram import Router, types
from aiogram.filters import Command

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.reply(
        "Привет! 👋 Отправь резюме — и ИИ подскажет, что улучшить и какие у тебя скрытые навыки.\n\n"
        "Форматы:\n"
        "• ссылка на резюме на hh.ru\n"
        "• файл PDF\n"
        "• файл Markdown (.md)"
    )


def register_handlers(dp):
    dp.include_router(router)
