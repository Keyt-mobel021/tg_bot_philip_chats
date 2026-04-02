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
    - заменяет визуально похожие символы (0→о, 3→з и т.п.)
    - приводит к нижнему регистру
    """
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
) -> dict | None:
    """
    Проверяет текст против фильтров.
    Возвращает None если нарушений нет.
    Возвращает dict если нарушение:
    {
        "pattern": str,          # паттерн фильтра
        "matched_text": str,     # что именно совпало в тексте
        "match_type": str,       # "regex", "regex_normalized", "fuzzy", "config"
    }
    """
    if not text:
        return None

    all_filters = (
        [f for f in global_filters if f.is_active] +
        [f for f in chat_filters if f.is_active]
    )
    if not all_filters:
        return None

    text_normalized = _normalize(text)
    text_lower = text.lower()

    # ── Проверка встроенных конфиг-паттернов ──
    for compiled in _CONFIG_PATTERNS:
        m = compiled.search(text)
        if m:
            logger.info(f"Config filter hit: pattern='{compiled.pattern}' text='{text[:60]}'")
            return {
                "pattern": compiled.pattern,
                "matched_text": m.group()[:100],
                "match_type": "config",
            }
        m = compiled.search(text_normalized)
        if m:
            logger.info(f"Config filter hit (normalized): pattern='{compiled.pattern}' text='{text[:60]}'")
            return {
                "pattern": compiled.pattern,
                "matched_text": m.group()[:100],
                "match_type": "config_normalized",
            }

    for flt in all_filters:
        pattern = flt.pattern

        # 1. Прямой regex
        try:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                logger.info(f"Filter hit (direct): pattern='{pattern}' text='{text[:60]}'")
                return {
                    "pattern": pattern,
                    "matched_text": m.group()[:100],
                    "match_type": "regex",
                }
        except re.error:
            logger.warning(f"Invalid regex pattern id={getattr(flt, 'id', '?')}: {pattern}")
            continue

        # 2. Regex по нормализованному тексту
        try:
            m = re.search(pattern, text_normalized, re.IGNORECASE)
            if m:
                logger.info(f"Filter hit (normalized): pattern='{pattern}' text='{text[:60]}'")
                return {
                    "pattern": pattern,
                    "matched_text": m.group()[:100],
                    "match_type": "regex_normalized",
                }
        except re.error:
            pass

        # 3. Нечёткое совпадение
        keywords = re.findall(r'[а-яёa-z]{5,}', pattern.lower())
        if not keywords:
            continue

        text_words = re.findall(r'[а-яёa-z]{4,}', text_lower)
        text_norm_words = re.findall(r'[а-яёa-z]{4,}', text_normalized)
        all_words = list(set(text_words + text_norm_words))

        for tw in all_words:
            for kw in keywords:
                if fuzz.ratio(tw, kw) >= fuzzy_threshold:
                    logger.info(f"Filter hit (fuzzy): '{tw}'~'{kw}' text='{text[:60]}'")
                    return {
                        "pattern": pattern,
                        "matched_text": f"{tw} ≈ {kw}",
                        "match_type": "fuzzy",
                    }

    return None