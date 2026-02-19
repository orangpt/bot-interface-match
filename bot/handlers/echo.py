from aiogram import Router, types

router = Router()


@router.message()
async def echo_message(message: types.Message):
    await message.reply(message.text)


def register_handlers(dp):
    dp.include_router(router)
