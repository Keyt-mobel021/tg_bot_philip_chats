import re
from fuzzywuzzy import fuzz
from loguru import logger
import models
import config


# Компилируем конфиг-паттерны один раз при старте
_CONFIG_PATTERNS = []
for _p in config.ALL_FILTER_PATTERNS:
    try:
        _CONFIG_PATTERNS.append(re.compile(_p, re.IGNORECASE))
    except re.error:
        pass


def _normalize(text: str) -> str:
    """
    Нормализует текст перед проверкой:
    - убирает пробелы, дефисы, скобки, точки между цифрами (для телефонов)
    - заменяет визуально похожие символы (0→о, 3→з и т.п.)
    - приводит к нижнему регистру
    """
    # Визуально похожие символы (латиница/цифры → кириллица и обратно)
    replacements = {
        '0': 'о', '3': 'з', '4': 'ч', '6': 'б', '8': 'в',
        '@': 'а', '$': 'с', '!': 'и', '1': 'i',
        'a': 'а', 'e': 'е', 'o': 'о', 'p': 'р', 'c': 'с',
        'x': 'х', 'y': 'у', 'k': 'к', 'm': 'м', 'b': 'в',
        'h': 'н', 'n': 'п', 't': 'т',
    }
    result = text.lower()
    for src, dst in replacements.items():
        result = result.replace(src, dst)
    return result


def _strip_separators(text: str) -> str:
    """Убирает все не-буквенно-цифровые символы — для проверки телефонов."""
    return re.sub(r'[\s\-\.\(\)\+\,\_]', '', text)



def check_text_against_filters(
    text: str,
    chat_filters: list,
    global_filters: list,
    fuzzy_threshold: int = 80,
) -> bool:
    """
    Проверяет текст против фильтров. Возвращает True если нарушение.

    Этапы проверки для каждого фильтра:
    1. Прямой regex по оригинальному тексту
    2. Regex по тексту без разделителей (ловит телефоны с пробелами/точками)
    3. Regex по нормализованному тексту (ловит замену букв цифрами)
    4. Нечёткое совпадение слов (fuzz)
    """
    if not text:
        return False
        
    all_filters = (
        [f for f in global_filters if f.is_active] +
        [f for f in chat_filters if f.is_active]
    )
    if not all_filters:
        return False

    text_stripped = _strip_separators(text)
    text_normalized = _normalize(text)
    text_norm_stripped = _strip_separators(text_normalized)
    text_lower = text.lower()

    # ── Проверка встроенных конфиг-паттернов (телефоны, email, ссылки и т.п.) ──
    for compiled in _CONFIG_PATTERNS:
        if compiled.search(text):
            logger.info(f"Config filter hit: pattern='{compiled.pattern}' text='{text[:60]}'")
            return True
        if compiled.search(text_stripped):
            logger.info(f"Config filter hit (stripped): pattern='{compiled.pattern}' text='{text[:60]}'")
            return True
        if compiled.search(text_normalized):
            logger.info(f"Config filter hit (normalized): pattern='{compiled.pattern}' text='{text[:60]}'")
            return True
        if compiled.search(text_norm_stripped):
            logger.info(f"Config filter hit (norm+stripped): pattern='{compiled.pattern}' text='{text[:60]}'")
            return True

    for flt in all_filters:
        pattern = flt.pattern

        # 1. Прямой regex по оригинальному тексту
        try:
            if re.search(pattern, text, re.IGNORECASE):
                logger.info(f"Filter hit (direct): pattern='{pattern}' text='{text[:60]}'")
                return True
        except re.error:
            logger.warning(f"Invalid regex pattern id={getattr(flt, 'id', '?')}: {pattern}")
            continue

        # 2. Regex по тексту без разделителей (телефоны вида +7 999 123 45 67)
        try:
            if re.search(pattern, text_stripped, re.IGNORECASE):
                logger.info(f"Filter hit (stripped): pattern='{pattern}' text='{text[:60]}'")
                return True
        except re.error:
            pass

        # 3. Regex по нормализованному тексту (замена букв цифрами/символами)
        try:
            if re.search(pattern, text_normalized, re.IGNORECASE):
                logger.info(f"Filter hit (normalized): pattern='{pattern}' text='{text[:60]}'")
                return True
            if re.search(pattern, text_norm_stripped, re.IGNORECASE):
                logger.info(f"Filter hit (norm+stripped): pattern='{pattern}' text='{text[:60]}'")
                return True
        except re.error:
            pass

        # 4. Нечёткое совпадение по словам
        keywords = re.findall(r'[а-яёa-z]{4,}', pattern.lower())
        if not keywords:
            continue

        text_words = re.findall(r'[а-яёa-z]{3,}', text_lower)
        text_norm_words = re.findall(r'[а-яёa-z]{3,}', text_normalized)
        all_words = list(set(text_words + text_norm_words))

        for tw in all_words:
            for kw in keywords:
                if fuzz.ratio(tw, kw) >= fuzzy_threshold:
                    logger.info(f"Filter hit (fuzzy): '{tw}'~'{kw}' text='{text[:60]}'")
                    return True
                
        # 5. Грубая проверка: извлекаем все цифры подряд группами 10-11 штук
        digits_only = re.sub(r'\D', '', text)
        # Ищем в тексте все последовательности цифр длиной 10+
        digit_groups = re.findall(r'\d{10,}', re.sub(r'\s', '', text.replace('-', '').replace('.', '').replace('(', '').replace(')', '').replace('+', '')))
        for group in digit_groups:
            # 11 цифр начинающихся на 7 или 8 — российский номер
            if len(group) >= 10 and group[0] in ('7', '8', '9'):
                logger.info(f"Filter hit (digits): group='{group}' text='{text[:60]}'")
                return True
            # 10 цифр начинающихся на 9 — мобильный без кода
            if len(group) == 10 and group[0] == '9':
                logger.info(f"Filter hit (digits): group='{group}' text='{text[:60]}'")
                return True

    return False