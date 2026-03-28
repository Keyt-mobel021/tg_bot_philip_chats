"""
Хендлеры: написать сообщение в чат + посмотреть историю.
Задача 1: при написании из истории — история остаётся видна, потом удаляется.
Задача 2 (новая): reply на сообщение от бота = ответ в чат.
Задача 4: часовой пояс МСК.
Задача 5 (новая): режим компании — при нарушении морозим всех клиентов.
Задача 7 (новая): пишем «чат заморожен» вместо «вы заморожены».
Задача 11: система непрочитанных сообщений.
"""
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from loguru import logger

import models
import config
from filters import CheckUser, PhotoFilter
from keyboards import ChatCD, ChatAction, HistoryCD, HistoryAction
from keyboards.kb import history_keyboard, cancel_keyboard
from states import SendMessageState
from utils.filters_check import check_text_against_filters
from utils.broadcast import broadcast_message_to_chat, notify_admins_violation

from . import *

router = Router()

_MAX_PAGE_CHARS = 3800
_MAX_MSG_BODY = 800


def _msk_dt(dt) -> str:
    """Форматирует datetime в строку МСК."""
    import datetime as _dt
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        # naive datetime — считаем UTC, переводим в МСК
        import pytz
        dt = pytz.utc.localize(dt).astimezone(config.TIMEZONE)
    else:
        dt = dt.astimezone(config.TIMEZONE)
    return dt.strftime("%d.%m %H:%M")


# ══════════════════════════════════════════════
#  Написать сообщение — из карточки чата
# ══════════════════════════════════════════════

@router.callback_query(ChatCD.filter(F.action == ChatAction.write), CheckUser())
async def cb_write_message(
    call: types.CallbackQuery,
    callback_data: ChatCD,
    state: FSMContext,
    user: models.UserTelegram,
):
    await _start_write(call, callback_data.chat_id, state, user, from_history=False)


# ══════════════════════════════════════════════
#  Задача 1: Написать из истории / ответить на рассылку
# ══════════════════════════════════════════════

@router.callback_query(ChatCD.filter(F.action == ChatAction.write_from_history), CheckUser())
async def cb_write_from_history(
    call: types.CallbackQuery,
    callback_data: ChatCD,
    state: FSMContext,
    user: models.UserTelegram,
):
    await _start_write(
        call, callback_data.chat_id, state, user,
        from_history=True,
        history_page=callback_data.page,
        history_msg_id=call.message.message_id,
    )


async def _start_write(
    call: types.CallbackQuery,
    chat_id: int,
    state: FSMContext,
    user: models.UserTelegram,
    from_history: bool,
    history_page: int = 0,
    history_msg_id: int | None = None,
):
    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)

    if not chat:
        await call.answer("Чат не найден", show_alert=True)
        return

    if chat.is_frozen:
        await call.answer("❄️ Чат заморожен — отправка сообщений недоступна", show_alert=True)
        return

    with models.connector:
        member = models.ChatMember.get_or_none(
            (models.ChatMember.user_id == user.id) &
            (models.ChatMember.chat_id == chat_id)
        )

    if not member:
        await call.answer("Вы не участник этого чата", show_alert=True)
        return

    if member.is_blocked:
        await call.answer("❄️ Чат временно заморожен", show_alert=True)
        return

    await state.set_state(SendMessageState.get_message)
    await state.update_data(
        chat_id=chat_id,
        from_history=from_history,
        history_page=history_page,
        history_msg_id=history_msg_id,
    )

    if from_history:
        # Сначала отправляем историю чата
        await _send_history_message(
            bot=call.bot,
            chat_id_tg=call.message.chat.id,
            chat=chat,
            page=0,
            member_id=None,
        )
        # Потом запрашиваем сообщение
        sent = await call.message.answer(
            "✏️ Напишите ваш ответ — текст, фото, видео или файл.\n\n"
            "Сообщение будет отправлено в чат.",
            reply_markup=cancel_keyboard(),
        )
        await state.update_data(prompt_msg_id=sent.message_id)
        await call.answer()
    else:
        await call.message.edit_text(
            "✏️ Отправьте сообщение — текст, фото, видео, файл или всё вместе.\n\n"
            "Можно отправить медиагруппой.",
            reply_markup=cancel_keyboard(),
        )
        await state.update_data(prompt_msg_id=call.message.message_id)
        await call.answer()


# ══════════════════════════════════════════════
#  ЗАДАЧА 2: Reply на сообщение от бота = ответ в чат
#  Если пользователь делает reply на сообщение бота,
#  у которого есть inline-кнопки с chat_id, бот
#  распознаёт это как сообщение в соответствующий чат.
# ══════════════════════════════════════════════

@router.message(F.reply_to_message, CheckUser())
async def handle_reply_to_bot(
    message: types.Message,
    state: FSMContext,
    user: models.UserTelegram,
    profile: models.Profile | None = None,
    is_admin_or_manager: bool = False,
):
    """
    Ловим reply на сообщение бота. Пытаемся определить chat_id
    из inline-кнопок оригинального сообщения.
    """
    reply = message.reply_to_message
    if not reply:
        return

    # Проверяем что это сообщение от бота (а не от другого пользователя)
    if not reply.from_user or not reply.from_user.is_bot:
        return

    # Ищем chat_id в inline-кнопках оригинального сообщения
    chat_id = _extract_chat_id_from_markup(reply.reply_markup)
    if not chat_id:
        return

    # Проверяем текущее состояние FSM — если уже в каком-то FSM, не перехватываем
    current_state = await state.get_state()
    if current_state is not None:
        return

    # Далее обрабатываем как обычное сообщение в чат
    text = message.text or message.caption or ""

    await _process_and_send(
        message=message,
        state=state,
        user=user,
        chat_id=chat_id,
        text=text,
        raw_messages=[message],
        from_history=False,
        history_page=0,
        history_msg_id=None,
        prompt_msg_id=None,
    )


def _extract_chat_id_from_markup(markup) -> int | None:
    """
    Извлекает chat_id из inline-клавиатуры сообщения бота.
    Ищет callback_data, содержащий chat_id в формате ChatCD.
    """
    if not markup or not hasattr(markup, 'inline_keyboard'):
        return None

    for row in markup.inline_keyboard:
        for button in row:
            if not button.callback_data:
                continue
            cb_data = button.callback_data
            # Ищем callback_data вида "chat:...:chat_id:NNN:..."
            # ChatCD prefix = "chat", формат: chat:action:chat_id:page
            if cb_data.startswith("chat:"):
                try:
                    parsed = ChatCD.unpack(cb_data)
                    if parsed.chat_id:
                        return parsed.chat_id
                except Exception:
                    pass
    return None


# ══════════════════════════════════════════════
#  Приём сообщения: медиагруппа
# ══════════════════════════════════════════════

@router.message(SendMessageState.get_message, CheckUser(), PhotoFilter())
async def handle_send_with_media(
    message: types.Message,
    state: FSMContext,
    album: list[types.Message],
    user: models.UserTelegram,
    profile: models.Profile | None = None,
):
    data = await state.get_data()
    chat_id = data.get("chat_id")
    if not chat_id:
        await state.clear()
        return

    first = album[0]
    await _process_and_send(
        message=first,
        state=state,
        user=user,
        chat_id=chat_id,
        text=first.caption or first.text or "",
        raw_messages=album,
        from_history=data.get("from_history", False),
        history_page=data.get("history_page", 0),
        history_msg_id=data.get("history_msg_id"),
        prompt_msg_id=data.get("prompt_msg_id"),
    )


# ══════════════════════════════════════════════
#  Приём сообщения: текст
# ══════════════════════════════════════════════

@router.message(SendMessageState.get_message, CheckUser())
async def handle_send_text(
    message: types.Message,
    state: FSMContext,
    user: models.UserTelegram,
    profile: models.Profile | None = None,
):
    data = await state.get_data()
    chat_id = data.get("chat_id")
    if not chat_id:
        await state.clear()
        return

    await _process_and_send(
        message=message,
        state=state,
        user=user,
        chat_id=chat_id,
        text=message.text or "",
        raw_messages=[message],
        from_history=data.get("from_history", False),
        history_page=data.get("history_page", 0),
        history_msg_id=data.get("history_msg_id"),
        prompt_msg_id=data.get("prompt_msg_id"),
    )


# ══════════════════════════════════════════════
#  Основная логика отправки
# ══════════════════════════════════════════════


def _extract_attachment(msg: types.Message, message_id: int) -> models.Attachment | None:
    file_id = None
    att_type = None

    if msg.photo:
        file_id = msg.photo[-1].file_id
        att_type = models.AttachmentType.PHOTO
    elif msg.video:
        file_id = msg.video.file_id
        att_type = models.AttachmentType.VIDEO
    elif msg.audio:
        file_id = msg.audio.file_id
        att_type = models.AttachmentType.AUDIO
    elif msg.voice:
        file_id = msg.voice.file_id
        att_type = models.AttachmentType.VOICE
    elif msg.video_note:
        file_id = msg.video_note.file_id
        att_type = models.AttachmentType.VIDEO_NOTE
    elif msg.document:
        file_id = msg.document.file_id
        att_type = models.AttachmentType.DOCUMENT

    if not file_id:
        return None

    return models.Attachment.create(
        message_id=message_id,
        id_file=file_id,
        attachment_type=att_type,
    )


async def _process_and_send(
    message: types.Message,
    state: FSMContext,
    user: models.UserTelegram,
    chat_id: int,
    text: str,
    raw_messages: list[types.Message],
    from_history: bool = False,
    history_page: int = 0,
    history_msg_id: int | None = None,
    prompt_msg_id: int | None = None,
):
    await state.clear()

    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        if not chat:
            await message.answer("Чат не найден.")
            return

        member = models.ChatMember.get_or_none(
            (models.ChatMember.user_id == user.id) &
            (models.ChatMember.chat_id == chat_id)
        )
        if not member:
            await message.answer("Вы не участник этого чата.")
            return

        # ЗАДАЧА 1: проверка заморозки
        if member.is_blocked:
            from text_templates import CHAT_FROZEN_VIOLATION_TEXT
            await message.answer(CHAT_FROZEN_VIOLATION_TEXT)
            return

        chat_filters = list(models.ChatFilter.select().where(
            (models.ChatFilter.chat_id == chat_id) &
            (models.ChatFilter.is_active == True)
        ))
        global_filters = list(models.GlobalFilter.select().where(
            models.GlobalFilter.is_active == True
        ))

    # ── Проверка фильтров ──────────────────────────────────────
    if text and not member.is_admin_or_manager and check_text_against_filters(text, chat_filters, global_filters):
        with models.connector:
            is_client = member.is_client
            company_id = member.company_id_id or 0
            is_company_mode = chat.company_mode

            if is_client:
                if is_company_mode:
                    # ЗАДАЧА 5: Режим компании — морозим ВСЕХ клиентов в этом чате
                    # (участники без профиля / с типом CLIENT)
                    models.ChatMember.update(is_blocked=True).where(
                        (models.ChatMember.chat_id == chat_id) &
                        (models.ChatMember.member_type == models.MemberType.CLIENT)
                    ).execute()
                elif company_id:
                    # Старое поведение: морозим по компании
                    models.ChatMember.update(is_blocked=True).where(
                        (models.ChatMember.chat_id == chat_id) &
                        (models.ChatMember.company_id == company_id)
                    ).execute()
                    models.Company.update(is_blocked=True).where(
                        models.Company.id == company_id
                    ).execute()
                else:
                    # Без режима компании и без company_id — морозим только нарушителя
                    member.is_blocked = True
                    member.save()
            else:
                if not member.is_admin_or_manager:
                    member.is_blocked = True
                    member.save()

        try:
            await message.delete()
        except Exception:
            pass

        # ЗАДАЧА 7: пишем «чат заморожен, идёт разбирательство»
        from text_templates import CHAT_FROZEN_VIOLATION_TEXT
        await message.answer(CHAT_FROZEN_VIOLATION_TEXT)

        await notify_admins_violation(
            message.bot, chat, member, text,
            is_client_violation=is_client,
            company_id=company_id,
            is_company_mode=is_company_mode,
        )
        return

    # ── Сохраняем сообщение и вложения ────────────────────────
    with models.connector:
        db_msg = models.Message.create(
            member_id=member.id,
            text=text[:4000] if text else None,
        )
        for msg in raw_messages:
            _extract_attachment(msg, db_msg.id)

    with models.connector:
        db_attachments = list(models.Attachment.select().where(
            models.Attachment.message_id == db_msg.id
        ))

    # ── Рассылка другим участникам ─────────────────────────────
    await broadcast_message_to_chat(
        bot=message.bot,
        chat=chat,
        sender_member=member,
        text=text or None,
        attachments=db_attachments or None,
        exclude_member_id=member.id,
    )

    # ── Задача 1+3: Возврат после отправки ────────────────────
    if from_history:
        try:
            await message.delete()
        except Exception:
            pass
        if prompt_msg_id:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
            except Exception:
                pass
        if history_msg_id:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=history_msg_id)
            except Exception:
                pass

        await _send_history_message(
            bot=message.bot,
            chat_id_tg=message.chat.id,
            chat=chat,
            page=0,
            member_id=member.id,
            prefix="✅ Сообщение отправлено!",
        )
    else:
        try:
            await message.delete()
        except Exception:
            pass
        await show_chat_detail(
            message, chat_id, user, is_admin_or_manager=False,
            prefix="✅ Сообщение отправлено!"
        )


async def _send_history_message(
    bot,
    chat_id_tg: int,
    chat: models.Chat,
    page: int,
    member_id: int | None = None,
    prefix: str = "",
):
    bot_user = await bot.get_me()
    bot_username = bot_user.username
    chat_id_db = chat.id
    chat_token = str(chat_id_db)

    with models.connector:
        all_messages = list(
            models.Message.select()
            .join(models.ChatMember)
            .where(
                (models.ChatMember.chat_id == chat_id_db) &
                (models.Message.has_forbidden == False)
            )
            .order_by(models.Message.date_create.asc())
        )

    if not all_messages:
        await bot.send_message(
            chat_id=chat_id_tg,
            text=(prefix + "\n\n" if prefix else "") + "📭 История пока пуста.",
            reply_markup=history_keyboard(chat_id_db, 0, 1),
        )
        return

    blocks = _build_message_blocks(all_messages, bot_username, chat_token)

    pages = _split_blocks_into_pages(blocks, _MAX_PAGE_CHARS)
    total_pages = len(pages)
    page = max(0, min(page, total_pages - 1))

    if member_id and all_messages:
        _mark_read(member_id, all_messages[-1].id)

    text_body = "\n\n".join(pages[page])
    header = (prefix + "\n\n" if prefix else "") + \
             f"📋 <b>История чата «{chat.title}»</b> (стр. {page + 1}/{total_pages})\n\n"
    full_text = header + text_body

    if len(full_text) > 4090:
        full_text = full_text[:4087] + "…"

    await bot.send_message(
        chat_id=chat_id_tg,
        text=full_text,
        reply_markup=history_keyboard(chat_id_db, page, total_pages),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# ══════════════════════════════════════════════
#  История сообщений
# ══════════════════════════════════════════════

@router.callback_query(ChatCD.filter(F.action == ChatAction.history), CheckUser())
async def cb_history(call: types.CallbackQuery, callback_data: ChatCD, user: models.UserTelegram):
    await _show_history(call, callback_data.chat_id, page=0, user_id=user.id)
    await call.answer()


@router.callback_query(HistoryCD.filter(F.action == HistoryAction.page), CheckUser())
async def cb_history_page(call: types.CallbackQuery, callback_data: HistoryCD, user: models.UserTelegram):
    await _show_history(call, callback_data.chat_id, page=callback_data.page, user_id=user.id)
    await call.answer()


async def _show_history(call: types.CallbackQuery, chat_id: int, page: int, user_id: int):
    bot_username = (await call.bot.get_me()).username
    chat_token = str(chat_id)

    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        if not chat:
            await call.answer("Чат не найден", show_alert=True)
            return

        all_messages = list(
            models.Message.select()
            .join(models.ChatMember)
            .where(
                (models.ChatMember.chat_id == chat_id) &
                (models.Message.has_forbidden == False)
            )
            .order_by(models.Message.date_create.asc())
        )

        member = models.ChatMember.get_or_none(
            (models.ChatMember.user_id == user_id) &
            (models.ChatMember.chat_id == chat_id)
        )
        member_id = member.id if member else None

    if not all_messages:
        await call.message.edit_text(
            "📭 Сообщений пока нет.",
            reply_markup=history_keyboard(chat_id, 0, 1),
        )
        return

    blocks = _build_message_blocks(all_messages, bot_username, chat_token)

    pages = _split_blocks_into_pages(blocks, _MAX_PAGE_CHARS)
    total_pages = len(pages)
    page = max(0, min(page, total_pages - 1))

    if member_id and all_messages:
        _mark_read(member_id, all_messages[-1].id)

    text_body = "\n\n".join(pages[page])
    header = f"📋 <b>История чата «{chat.title}»</b> (стр. {page + 1}/{total_pages})\n\n"
    full_text = header + text_body

    if len(full_text) > 4090:
        full_text = full_text[:4087] + "…"

    await call.message.edit_text(
        full_text,
        reply_markup=history_keyboard(chat_id, page, total_pages),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# ══════════════════════════════════════════════
#  Задача 11: отметить прочитанным
# ══════════════════════════════════════════════

def _mark_read(member_id: int, last_message_id: int):
    """Обновляет или создаёт запись о прочтении для участника."""
    try:
        with models.connector:
            existing = models.MessageRead.get_or_none(
                models.MessageRead.member_id == member_id
            )
            if existing:
                if existing.last_read_message_id < last_message_id:
                    existing.last_read_message_id = last_message_id
                    import datetime
                    existing.date_read = datetime.datetime.utcnow()
                    existing.save()
            else:
                import datetime
                models.MessageRead.create(
                    member_id=member_id,
                    last_read_message_id=last_message_id,
                    date_read=datetime.datetime.utcnow(),
                )
    except Exception as e:
        logger.warning(f"_mark_read error: {e}")


def get_unread_count(member_id: int, chat_id: int) -> int:
    """Возвращает количество непрочитанных сообщений для участника в чате."""
    try:
        with models.connector:
            read_mark = models.MessageRead.get_or_none(
                models.MessageRead.member_id == member_id
            )
            last_read_id = read_mark.last_read_message_id if read_mark else 0

            count = (
                models.Message.select()
                .join(models.ChatMember)
                .where(
                    (models.ChatMember.chat_id == chat_id) &
                    (models.Message.id > last_read_id)
                )
                .count()
            )
            return count
    except Exception as e:
        logger.warning(f"get_unread_count error: {e}")
        return 0


# ══════════════════════════════════════════════
#  Вспомогательные функции
# ══════════════════════════════════════════════

def _build_message_blocks(all_messages, bot_username: str, chat_token: str) -> list[str]:
    """Формирует список текстовых блоков по одному на сообщение."""
    blocks: list[str] = []
    for msg in all_messages:
        try:
            with models.connector:
                member = msg.member_id
                dt = _msk_dt(msg.date_create)
                name = member.display_name
                attachments = list(models.Attachment.select().where(
                    models.Attachment.message_id == msg.id
                ))

            body_parts = []
            if msg.text:
                body_text = msg.text[:_MAX_MSG_BODY]
                if len(msg.text) > _MAX_MSG_BODY:
                    body_text += "…"
                body_parts.append(body_text)

            if attachments:
                att_str = _format_attachments(attachments, bot_username, chat_token, msg.id)
                if att_str:
                    body_parts.append(att_str)

            body = "\n".join(body_parts) if body_parts else "—"
            blocks.append(f"<b>{name}</b> · {dt}\n{body}")
        except Exception as e:
            logger.warning(f"history: error rendering message {msg.id}: {e}")
            blocks.append("—")
    return blocks


def _media_link(bot_username: str, chat_token: str, message_id: int) -> str:
    return f"https://t.me/{bot_username}?start=media_{chat_token}_{message_id}"


def _format_attachments(attachments: list, bot_username: str, chat_token: str, message_id: int) -> str:
    if not attachments:
        return ""

    type_labels = {
        models.AttachmentType.PHOTO: "Фото",
        models.AttachmentType.VIDEO: "Видео",
        models.AttachmentType.AUDIO: "Аудио",
        models.AttachmentType.VOICE: "Голосовое",
        models.AttachmentType.VIDEO_NOTE: "Видеокружок",
        models.AttachmentType.DOCUMENT: "Файл",
        models.AttachmentType.STICKER: "Стикер",
    }
    counts: dict[str, int] = {}
    for a in attachments:
        label = type_labels.get(a.attachment_type, "Файл")
        counts[label] = counts.get(label, 0) + 1

    summary = ", ".join(f"({cnt}) {label}" for label, cnt in counts.items())
    link = _media_link(bot_username, chat_token, message_id)
    return f'📎 <a href="{link}">{summary}</a>'


def _split_blocks_into_pages(blocks: list[str], max_chars: int) -> list[list[str]]:
    pages: list[list[str]] = []
    current_page: list[str] = []
    current_len = 0
    separator_len = 2

    for block in blocks:
        block_len = len(block)
        add_len = block_len + (separator_len if current_page else 0)

        if current_page and current_len + add_len > max_chars:
            pages.append(current_page)
            current_page = [block]
            current_len = block_len
        else:
            current_page.append(block)
            current_len += add_len

    if current_page:
        pages.append(current_page)

    pages.reverse()

    return pages if pages else [[]]


# ══════════════════════════════════════════════
#  Диплинк media_<chat_id>_<message_id>
# ══════════════════════════════════════════════

async def send_message_media(message: types.Message, msg_id: int, user: models.UserTelegram):
    with models.connector:
        db_msg = models.Message.get_or_none(models.Message.id == msg_id)
        if not db_msg:
            await message.answer("❌ Сообщение не найдено.")
            return

        member = db_msg.member_id
        chat_id = member.chat_id_id

        user_member = models.ChatMember.get_or_none(
            (models.ChatMember.user_id == user.id) &
            (models.ChatMember.chat_id == chat_id)
        )
        if not user_member:
            await message.answer("❌ У вас нет доступа к этому чату.")
            return

        attachments = list(models.Attachment.select().where(
            models.Attachment.message_id == msg_id
        ))

    if not attachments:
        await message.answer("📭 Вложений в этом сообщении нет.")
        return

    if db_msg.text:
        await message.answer(
            f"💬 <b>Текст сообщения:</b>\n\n{db_msg.text}",
            parse_mode="HTML",
        )

    from aiogram.types import InputMediaPhoto, InputMediaVideo

    photos = [a for a in attachments if a.attachment_type == models.AttachmentType.PHOTO]
    videos = [a for a in attachments if a.attachment_type == models.AttachmentType.VIDEO]
    others = [a for a in attachments
              if a.attachment_type not in (models.AttachmentType.PHOTO, models.AttachmentType.VIDEO)]

    if photos:
        if len(photos) == 1:
            await message.answer_photo(photo=photos[0].id_file)
        else:
            media = [InputMediaPhoto(media=a.id_file) for a in photos]
            await message.bot.send_media_group(chat_id=message.chat.id, media=media)

    if videos:
        if len(videos) == 1:
            await message.answer_video(video=videos[0].id_file)
        else:
            media = [InputMediaVideo(media=a.id_file) for a in videos]
            await message.bot.send_media_group(chat_id=message.chat.id, media=media)

    for a in others:
        t = a.attachment_type
        if t == models.AttachmentType.AUDIO:
            await message.answer_audio(audio=a.id_file)
        elif t == models.AttachmentType.VOICE:
            await message.answer_voice(voice=a.id_file)
        elif t == models.AttachmentType.VIDEO_NOTE:
            await message.answer_video_note(video_note=a.id_file)
        else:
            await message.answer_document(document=a.id_file)