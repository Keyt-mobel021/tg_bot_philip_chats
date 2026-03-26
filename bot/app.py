import asyncio
import config
import models

from loads import bot
from handlers import start, chats, chat_messages, members, staff, autoconnect, filters_handler

from aiogram import Bot, Dispatcher, types, exceptions, F
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from middleware import *
from middleware.states_ware import *

from loguru import logger

dp = Dispatcher(storage=MemoryStorage())


def registration_routers(dp: Dispatcher):
    dp.message.middleware(SaveStateMiddleware())
    dp.callback_query.middleware(SaveStateMiddleware())

    dp.include_router(start.router)
    dp.include_router(chats.router)
    dp.include_router(chat_messages.router)
    dp.include_router(members.router)
    dp.include_router(staff.router)
    dp.include_router(autoconnect.router)
    dp.include_router(filters_handler.router)


# -=-=- Выполняется при запуске бота -=-=-
async def main():
    registration_routers(dp)

    # Запускаем бота и пропускаем все накопленные входящие
    await bot.delete_webhook(drop_pending_updates=True)
    # Подгружаем состояния пользователей из базы
    await get_data_states(dp, bot)

    try:
        logger.success('Start Bot')

        await dp.start_polling(bot)
    except exceptions.TelegramNetworkError as __err:
        logger.critical(f"Network_Error: {__err}")
    except Exception as _ex:
        logger.critical(f"Exception_Error: {_ex}")


if __name__ == "__main__":
    asyncio.run(main())