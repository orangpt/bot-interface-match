from aiogram import Router, types
from aiogram.filters import Command

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Привет! 👋 Я живу внутри Django 😎")


def register_handlers(dp):
    dp.include_router(router)
