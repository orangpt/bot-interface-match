from aiogram import Dispatcher
from . import start, echo, resume


def register_handlers(dp: Dispatcher):
    start.register_handlers(dp)
    resume.register_handlers(dp)
    echo.register_handlers(dp)
