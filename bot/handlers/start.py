from aiogram import Router, types
from aiogram.filters import Command

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Добрый день! 👋 Вы общаетесь с ботом Sigma Lab")


def register_handlers(dp):
    dp.include_router(router)
