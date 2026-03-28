import os
from pathlib import Path
import pytz


# -=-=- Путь к проекту -=-=-
PATH_PROJECT = Path(__file__).resolve().parent

BOT_USERNAME = "Konstructora_bot"

# Часовой пояс для отображения дат (МСК)
TIMEZONE = pytz.timezone("Europe/Moscow")

# Пагинация
PAGE_SIZE = 10
MESSAGES_PAGE_SIZE = 5

# Порог нечеткого совпадения по умолчанию
DEFAULT_FUZZY_THRESHOLD = 80


# ══════════════════════════════════════════════
#  Готовые regex-шаблоны фильтров (КОНСЕРВАТИВНЫЕ)
#  Задача 3: сильно уменьшен набор — только самые явные паттерны,
#  чтобы не блокировать обычные сообщения с числами/датами.
# ══════════════════════════════════════════════
 
# Телефонные номера — только самые явные форматы:
PHONE_PATTERNS = [
    # +7 (999) 123-45-67 или +7 999 123 45 67 (именно с +7 или 8 и далее 10 цифр)
    r'(?:\+7|8)[\s\-\.\(\)]*\(?\d{3}\)?[\s\-\.]*\d{3}[\s\-\.]*\d{2}[\s\-\.]*\d{2}',
    # 10 цифр подряд начиная с 9 (мобильный без кода)
    r'\b9\d{9}\b',
    # 11 цифр подряд начиная с 7 или 8
    r'\b[78]\d{10}\b',
]
 
# Email-адреса
EMAIL_PATTERNS = [
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
]
 
# Ссылки — только явные URL
URL_PATTERNS = [
    r'https?://[^\s]+',
    r'www\.[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}[^\s]*',
]
 
# Мессенджеры — только явные упоминания с контактом
MESSENGER_PATTERNS = [
    r't\.me/[a-zA-Z0-9_]{3,}',
    r'(?:whatsapp|wa\.me)[:\s/]*[\+\d]{10,}',
]
 
# Нецензурная лексика (базовый набор)
OBSCENE_PATTERNS = [
    r'\bхуй\w*\b',
    r'\bпизд\w*\b',
    r'\bблядь\w*\b',
    r'\bеб[аоуи]\w*\b',
    r'\bсука\b',
    r'\bмудак\w*\b',
    r'\bпидор\w*\b',
]
 
# Все шаблоны вместе (удобно для массовой вставки)
ALL_FILTER_PATTERNS = (
    PHONE_PATTERNS
    + EMAIL_PATTERNS
    + URL_PATTERNS
    + MESSENGER_PATTERNS
    + OBSCENE_PATTERNS
)