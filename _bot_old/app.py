import asyncio
import config
import models
from loguru import logger

from aiogram import Bot, Dispatcher, types, exceptions
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from handlers import admin, group


def setup_logging():
    logger.add(
        "logs/bot.log",
        format="{time} | {level} | {message}",
        level="DEBUG",
        rotation="10 MB",
        compression="zip",
        serialize=False
    )


def register_routers(dp: Dispatcher):
    # Сначала групповые хендлеры (только для групп)
    dp.include_router(group.router)
    # Потом админские (для личного чата)
    dp.include_router(admin.router)


async def main():
    setup_logging()
    models.init_db()

    bot = Bot(
        token=config.TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )

    dp = Dispatcher(storage=MemoryStorage())
    register_routers(dp)

    await bot.delete_webhook(drop_pending_updates=True)

    logger.success("Bot started!")

    try:
        await dp.start_polling(bot)
    except exceptions.TelegramNetworkError as e:
        logger.critical(f"Network error: {e}")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    import os
    os.makedirs("logs", exist_ok=True)
    asyncio.run(main())
