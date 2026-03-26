from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

import os
from dotenv import load_dotenv

from loguru import logger
import config


# -=-=- Загружаем переменные окружения -=-=-
load_dotenv('.env')

# -=-=- Логирование ошибок -=-=-
logger.add(os.path.join(config.PATH_PROJECT, 'log', 'logging.log'), format="{time} | {level} | {message}", level="DEBUG", compression='zip', serialize=True)

# -=-=- Loaded Bot Telegram -=-=-
bot = Bot(token=os.getenv("TOKEN_TELEGA"), default=DefaultBotProperties(parse_mode="HTML"))