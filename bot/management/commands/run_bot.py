import asyncio
from aiogram import Bot, Dispatcher
from django.core.management.base import BaseCommand
from bot.config import BOT_TOKEN
from bot.handlers import register_handlers


class Command(BaseCommand):
    help = "Запуск Telegram-бота"

    def handle(self, *args, **options):
        asyncio.run(self.run_bot())

    async def run_bot(self):
        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher()
        register_handlers(dp)

        self.stdout.write(self.style.SUCCESS("🤖 Бот запущен"))
        await dp.start_polling(bot)
