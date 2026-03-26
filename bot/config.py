import os
from pathlib import Path


# -=-=- Путь к проекту -=-=-
PATH_PROJECT = Path(__file__).resolve().parent

BOT_USERNAME = "Konstructora_bot"

# Пагинация
PAGE_SIZE = 10
MESSAGES_PAGE_SIZE = 5

# Порог нечеткого совпадения по умолчанию
DEFAULT_FUZZY_THRESHOLD = 80