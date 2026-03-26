import re
from aiogram import types, Router, F
from aiogram.filters import Command
from fuzzywuzzy import fuzz
import models
from aiogram.filters import IS_MEMBER, IS_NOT_MEMBER
from aiogram import F
from loguru import logger
import config

router = Router()

# Принимаем только сообщения из групп
router.message.filter(F.chat.type.in_({"group", "supergroup"}))


def check_message_filters(text: str, filters: list[models.ChatFilter], fuzzy_threshold: int) -> bool:
    """
    Проверяет сообщение на соответствие фильтрам.
    Возвращает True если сообщение нужно удалить.
    
    Логика:
    1. Если regex совпадает — удаляем сразу
    2. Дополнительно проверяем нечеткое совпадение по ключевым словам из паттернов
    """
    if not text:
        return False

    text_lower = text.lower()

    for chat_filter in filters:
        if not chat_filter.is_active:
            continue

        pattern = chat_filter.pattern

        # 1. Прямая проверка regex
        try:
            if re.search(pattern, text, re.IGNORECASE):
                logger.info(f"Regex match: pattern='{pattern}' text='{text[:50]}'")
                return True
        except re.error:
            logger.warning(f"Invalid regex pattern in filter {chat_filter.id}: {pattern}")
            continue

        # 2. Нечеткое совпадение: извлекаем «слова» из паттерна (буквенные токены)
        # Берем все буквенные слова длиной >= 4 из паттерна как ключевые слова
        keywords = re.findall(r'[а-яёa-z]{4,}', pattern.lower())
        if not keywords:
            continue

        # Разбиваем текст на слова
        text_words = re.findall(r'[а-яёa-z]{3,}', text_lower)
        if not text_words:
            continue

        # Считаем сколько слов из текста нечетко совпадают с ключевыми словами фильтра
        matched_words = 0
        for tw in text_words:
            for kw in keywords:
                score = fuzz.ratio(tw, kw)
                if score >= fuzzy_threshold:
                    matched_words += 1
                    break  # Это слово уже засчитано

        # Если больше 0 ключевых слов нашли совпадение — удаляем
        if matched_words > 0:
            logger.info(f"Fuzzy match: matched_words={matched_words}, threshold={fuzzy_threshold}, text='{text[:50]}'")
            return True

    return False


@router.message(Command("start"))
async def cmd_start_group(message: types.Message):
    """Регистрирует группу в базе при вводе /start"""
    chat = message.chat
    with models.connector:
        existing = models.ChatGroup.get_or_none(models.ChatGroup.id == chat.id)
        if not existing:
            models.ChatGroup.create(
                id=chat.id,
                title=chat.title,
                username=getattr(chat, 'username', None),
                is_group=True,
                is_active=True,
            )
            await message.answer("✅ Чат зарегистрирован! Бот начнёт фильтровать сообщения.")
            logger.info(f"New group registered: {chat.id} ({chat.title})")
        else:
            # Обновляем название если изменилось
            existing.title = chat.title
            existing.save()
            await message.answer("ℹ️ Этот чат уже зарегистрирован.")


@router.message(F.migrate_to_chat_id)
async def on_group_migrate(message: types.Message):
    old_id = message.chat.id
    new_id = message.migrate_to_chat_id

    logger.info(f"Group migrated: {old_id} -> {new_id}")

    with models.connector:
        chat = models.ChatGroup.get_or_none(models.ChatGroup.id == old_id)
        if chat:
            # Обновляем ID на новый
            models.ChatGroup.update(id=new_id).where(models.ChatGroup.id == old_id).execute()
            logger.info(f"DB updated: chat id {old_id} -> {new_id}")
        else:
            # Создаём если не было
            models.ChatGroup.create(
                id=new_id,
                title=message.chat.title,
                username=getattr(message.chat, 'username', None),
                is_group=True,
                is_active=True,
            )

@router.message(F.text)
async def filter_group_messages(message: types.Message):
    chat_id = message.chat.id
    text = message.text

    logger.debug(f"Message received | chat_id={chat_id} | type={message.chat.type} | text='{text[:50]}'")

    with models.connector:
        chat = models.ChatGroup.get_or_none(models.ChatGroup.id == chat_id)
        logger.debug(f"Chat found in DB: {chat is not None}")

        if not chat or not chat.is_active:
            logger.debug(f"Chat not found or inactive: {chat_id}")
            return

        filters = list(models.ChatFilter.select().where(
            (models.ChatFilter.chat_id == chat_id) &
            (models.ChatFilter.is_active == True)
        ))

    if not filters:
        return

    should_delete = check_message_filters(text, filters, chat.fuzzy_threshold)

    if should_delete:
        try:
            await message.delete()
            logger.info(f"Message deleted | chat={chat_id} | user={message.from_user.id} | text='{text[:100]}'")
        except Exception as e:
            logger.warning(f"Failed to delete message: {e}")
            return

        user = message.from_user
        
        # Баним пользователя в группе
        try:
            await message.bot.ban_chat_member(chat_id=chat_id, user_id=user.id)
            ban_status = "🔨 Заблокирован"
        except Exception as e:
            ban_status = f"⚠️ Не удалось заблокировать: {e}"
            logger.warning(f"Failed to ban user {user.id} in chat {chat_id}: {e}")

        # Сохраняем в базу
        with models.connector:
            already = models.BlockedUser.get_or_none(
                (models.BlockedUser.user_id == user.id) &
                (models.BlockedUser.chat_id == chat_id)
            )
            if not already:
                models.BlockedUser.create(
                    user_id=user.id,
                    full_name=user.full_name,
                    username=user.username,
                    chat_id=chat_id,
                    trigger_message=text[:500]
                )

        # Уведомляем администраторов
        username_str = f"@{user.username}" if user.username else f"tg://user?id={user.id}"
        notify_text = (
            f"🚨 <b>Заблокировано сообщение</b>\n\n"
            f"👤 Пользователь: <a href='tg://user?id={user.id}'>{user.full_name}</a> ({username_str})\n"
            f"💬 Чат: <b>{chat.title}</b> (<code>{chat_id}</code>)\n"
            f"📝 Сообщение:\n<blockquote>{text[:400]}</blockquote>\n\n"
            f"{ban_status}"
        )

        with models.connector:
            admins = list(models.AdminUser.select())

        admin_ids = [a.id for a in admins] if admins else config.ADMIN_IDS

        for admin_id in admin_ids:
            try:
                await message.bot.send_message(chat_id=admin_id, text=notify_text)
            except Exception as e:
                logger.warning(f"Failed to notify admin {admin_id}: {e}")