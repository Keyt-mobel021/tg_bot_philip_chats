import re
from fuzzywuzzy import fuzz
from loguru import logger
import models


def check_text_against_filters(text: str, chat_filters: list, global_filters: list,
                                fuzzy_threshold: int = 80) -> bool:
    """
    Проверяет текст сообщения против фильтров чата и глобальных.
    Возвращает True если сообщение нарушает фильтр.
    """
    if not text:
        return False

    all_filters = [f for f in global_filters if f.is_active] + \
                  [f for f in chat_filters if f.is_active]

    text_lower = text.lower()

    for flt in all_filters:
        pattern = flt.pattern

        # Проверка regex
        try:
            if re.search(pattern, text, re.IGNORECASE):
                logger.info(f"Regex match: pattern='{pattern}' text='{text[:50]}'")
                return True
        except re.error:
            logger.warning(f"Invalid regex pattern {getattr(flt, 'id', '?')}: {pattern}")
            continue

        # Нечёткое совпадение по ключевым словам
        keywords = re.findall(r'[а-яёa-z]{4,}', pattern.lower())
        if not keywords:
            continue

        text_words = re.findall(r'[а-яёa-z]{3,}', text_lower)
        if not text_words:
            continue

        for tw in text_words:
            for kw in keywords:
                if fuzz.ratio(tw, kw) >= fuzzy_threshold:
                    logger.info(f"Fuzzy match: '{tw}' ~ '{kw}' text='{text[:50]}'")
                    return True

    return False