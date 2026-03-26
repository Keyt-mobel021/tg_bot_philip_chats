"""
Хендлеры: написать сообщение в чат + посмотреть историю.
"""
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart
from loguru import logger

import models
import config
from filters import CheckUser, PhotoFilter
from keyboards import ChatCD, ChatAction, HistoryCD, HistoryAction
from keyboards.kb import history_keyboard, chat_detail_keyboard, cancel_keyboard
from states import SendMessageState
from utils.filters_check import check_text_against_filters
from utils.broadcast import broadcast_message_to_chat, notify_admins_violation

from . import *

router = Router()

# ══════════════════════════════════════════════
#  Константы
# ══════════════════════════════════════════════

# Максимальная длина текста одного сообщения в истории (с учётом заголовка страницы и разделителей)
_MAX_PAGE_CHARS = 3800
# Максимальная длина тела одного сообщения при отображении
_MAX_MSG_BODY = 800


# ══════════════════════════════════════════════
#  ЗАДАЧА 2б: диплинк media_<chat_connect_token>_<message_id>
# ══════════════════════════════════════════════

def _media_link(bot_username: str, chat_token: str, message_id: int) -> str:
    return f"https://t.me/{bot_username}?start=media_{chat_token}_{message_id}"


def _format_attachments(attachments: list, bot_username: str, chat_token: str, message_id: int) -> str:
    """
    ЗАДАЧА 2а: Формирует строку вида «📎 (2) Фото, (1) Видео» со ссылкой на медиа.
    """
    if not attachments:
        return ""

    counts: dict[str, int] = {}
    type_labels = {
        models.AttachmentType.PHOTO: "Фото",
        models.AttachmentType.VIDEO: "Видео",
        models.AttachmentType.AUDIO: "Аудио",
        models.AttachmentType.VOICE: "Голосовое",
        models.AttachmentType.VIDEO_NOTE: "Видеокружок",
        models.AttachmentType.DOCUMENT: "Файл",
        models.AttachmentType.STICKER: "Стикер",
    }
    for a in attachments:
        label = type_labels.get(a.attachment_type, "Файл")
        counts[label] = counts.get(label, 0) + 1

    parts = [f"({cnt}) {label}" for label, cnt in counts.items()]
    summary = ", ".join(parts)

    link = _media_link(bot_username, chat_token, message_id)
    return f'📎 <a href="{link}">{summary}</a>'


# ══════════════════════════════════════════════
#  Написать сообщение
# ══════════════════════════════════════════════
@router.callback_query(ChatCD.filter(F.action == ChatAction.write), CheckUser())
async def cb_write_message(call: types.CallbackQuery, callback_data: ChatCD, state: FSMContext, user: models.UserTelegram):
    chat_id = callback_data.chat_id

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
        await call.answer("🔒 Вы заморожены в этом чате", show_alert=True)
        return

    await state.set_state(SendMessageState.get_message)
    await state.update_data(chat_id=chat_id)

    await call.message.edit_text(
        "✏️ Отправьте сообщение — текст, фото, видео, файл или всё вместе.\n\n"
        "Можно отправить медиагруппой.",
        reply_markup=cancel_keyboard(),
    )
    await call.answer()


@router.message(SendMessageState.get_message, CheckUser(), PhotoFilter())
async def handle_send_with_media(message: types.Message, state: FSMContext, album: list[types.Message], user: models.UserTelegram, profile: models.Profile | None = None):
    data = await state.get_data()
    chat_id = data.get("chat_id")
    if not chat_id:
        await state.clear()
        return

    first = album[0]
    text = first.caption or first.text or ""

    await _process_and_send(
        message=first,
        state=state,
        user=user,
        chat_id=chat_id,
        text=text,
        raw_messages=album,
    )


@router.message(SendMessageState.get_message, CheckUser())
async def handle_send_text(message: types.Message, state: FSMContext, user: models.UserTelegram, profile: models.Profile | None = None):
    data = await state.get_data()
    chat_id = data.get("chat_id")
    if not chat_id:
        await state.clear()
        return

    text = message.text or ""

    await _process_and_send(
        message=message,
        state=state,
        user=user,
        chat_id=chat_id,
        text=text,
        raw_messages=[message],
    )


async def _process_and_send(message: types.Message, state: FSMContext, user: models.UserTelegram, chat_id: int, text: str, raw_messages: list[types.Message]):
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

        chat_filters = list(models.ChatFilter.select().where(
            (models.ChatFilter.chat_id == chat_id) &
            (models.ChatFilter.is_active == True)
        ))
        global_filters = list(models.GlobalFilter.select().where(
            models.GlobalFilter.is_active == True
        ))

    # Проверка фильтров
    if text and check_text_against_filters(text, chat_filters, global_filters):
        with models.connector:
            member.is_blocked = True
            member.save()
            if member.profile_id_id:
                p = member.profile_id
                p.is_blocked = True
                p.save()

        with models.connector:
            models.Message.create(
                member_id=member.id,
                text=text[:4000],
                has_forbidden=True,
            )

        await message.answer(
            "🚫 Ваше сообщение содержит запрещённые материалы.\n"
            "Вы заморожены в этом чате. Обратитесь к администратору."
        )
        await notify_admins_violation(message.bot, chat, member, text)
        return

    # Сохраняем сообщение
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

    await broadcast_message_to_chat(
        bot=message.bot,
        chat=chat,
        sender_member=member,
        text=text or None,
        attachments=db_attachments or None,
        exclude_member_id=member.id,
    )

    await show_chat_detail(message, chat_id, user, is_admin_or_manager=False, prefix="✅ Сообщение отправлено!")


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
    """
    ЗАДАЧА 2 + ЗАДАЧА 3:
    - Вложения отображаются как «(2) Фото, (1) Видео» со ссылкой на медиа
    - Умная пагинация: сообщения разбиваются по символам, не по кол-ву
    - Если одно сообщение само по себе длинное — оно занимает свою страницу
    """
    bot_username = (await call.bot.get_me()).username

    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        if not chat:
            await call.answer("Чат не найден", show_alert=True)
            return

        # Получаем токен чата для медиа-диплинков (берём connect_token любого члена чата как идентификатор)
        # Используем chat.id как часть токена — он стабилен
        chat_token = str(chat.id)

        # Загружаем все сообщения (от новых к старым — для пагинации)
        all_messages = list(
            models.Message.select()
            .join(models.ChatMember)
            .where(models.ChatMember.chat_id == chat_id)
            .order_by(models.Message.date_create.desc())
        )

    if not all_messages:
        await call.message.edit_text(
            "📭 Сообщений пока нет.",
            reply_markup=history_keyboard(chat_id, 0, 1),
        )
        return

    # Собираем блоки текста для каждого сообщения
    blocks: list[str] = []
    for msg in reversed(all_messages):  # от старых к новым для отображения
        try:
            with models.connector:
                member = msg.member_id
                dt = msg.date_create.strftime("%d.%m %H:%M")
                name = member.display_name

                attachments = list(models.Attachment.select().where(
                    models.Attachment.message_id == msg.id
                ))

            # ЗАДАЧА 2а: тело сообщения
            body_parts = []
            if msg.text:
                body_text = msg.text[:_MAX_MSG_BODY]
                if len(msg.text) > _MAX_MSG_BODY:
                    body_text += "…"
                body_parts.append(body_text)

            # ЗАДАЧА 2а+2б: форматируем вложения
            if attachments:
                att_str = _format_attachments(attachments, bot_username, chat_token, msg.id)
                if att_str:
                    body_parts.append(att_str)

            body = "\n".join(body_parts) if body_parts else "—"
            blocks.append(f"<b>{name}</b> · {dt}\n{body}")
        except Exception as e:
            logger.warning(f"history: error rendering message {msg.id}: {e}")
            blocks.append("—")

    # ЗАДАЧА 3: умная пагинация по символам
    pages: list[list[str]] = _split_blocks_into_pages(blocks, _MAX_PAGE_CHARS)
    total_pages = len(pages)

    # Ограничиваем страницу
    page = max(0, min(page, total_pages - 1))

    # Страница отображается от новых к старым — переворачиваем
    page_blocks = list(reversed(pages[page]))
    text_body = "\n\n".join(page_blocks)
    header = f"📋 <b>История чата «{chat.title}»</b> (стр. {page + 1}/{total_pages})\n\n"

    full_text = header + text_body

    # Финальная защита от превышения лимита Telegram (4096 символов)
    if len(full_text) > 4090:
        full_text = full_text[:4087] + "…"

    await call.message.edit_text(
        full_text,
        reply_markup=history_keyboard(chat_id, page, total_pages),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


def _split_blocks_into_pages(blocks: list[str], max_chars: int) -> list[list[str]]:
    """
    ЗАДАЧА 3: Разбивает список блоков сообщений на страницы по символам.
    Порядок внутри каждой страницы: от старых к новым (индексы растут).
    Если один блок сам по себе длиннее max_chars — он занимает отдельную страницу.
    """
    pages: list[list[str]] = []
    current_page: list[str] = []
    current_len = 0
    separator_len = 2  # "\n\n"

    for block in blocks:
        block_len = len(block)
        add_len = block_len + (separator_len if current_page else 0)

        if current_page and current_len + add_len > max_chars:
            # Текущая страница заполнена — сохраняем и начинаем новую
            pages.append(current_page)
            current_page = [block]
            current_len = block_len
        else:
            current_page.append(block)
            current_len += add_len

    if current_page:
        pages.append(current_page)

    # Страницы должны идти от новых к старым (последняя страница = самые новые)
    # blocks уже отсортированы от старых к новым, поэтому переворачиваем список страниц
    pages.reverse()

    return pages if pages else [[]]


# ══════════════════════════════════════════════
#  ЗАДАЧА 2б: Диплинк media_<chat_id>_<message_id>
#  Обработчик в start.py — здесь только хелпер отправки медиа
# ══════════════════════════════════════════════

async def send_message_media(message: types.Message, msg_id: int, user: models.UserTelegram):
    """
    Отправляет все вложения конкретного сообщения + текст.
    Вызывается из start.py при обработке диплинка media_<chat_id>_<msg_id>.
    """
    with models.connector:
        db_msg = models.Message.get_or_none(models.Message.id == msg_id)
        if not db_msg:
            await message.answer("❌ Сообщение не найдено.")
            return

        member = db_msg.member_id
        chat_id = member.chat_id_id

        # Проверяем доступ пользователя к чату
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

    # Отправляем текст сообщения (если есть)
    if db_msg.text:
        await message.answer(
            f"💬 <b>Текст сообщения:</b>\n\n{db_msg.text}",
            parse_mode="HTML",
        )

    # Отправляем вложения по одному (чтобы не ограничиваться медиагруппой)
    from aiogram.types import InputMediaPhoto, InputMediaVideo

    photos = [a for a in attachments if a.attachment_type == models.AttachmentType.PHOTO]
    videos = [a for a in attachments if a.attachment_type == models.AttachmentType.VIDEO]
    others = [a for a in attachments
              if a.attachment_type not in (models.AttachmentType.PHOTO, models.AttachmentType.VIDEO)]

    # Фото медиагруппой
    if photos:
        if len(photos) == 1:
            await message.answer_photo(photo=photos[0].id_file)
        else:
            media = [InputMediaPhoto(media=a.id_file) for a in photos]
            await message.bot.send_media_group(chat_id=message.chat.id, media=media)

    # Видео медиагруппой
    if videos:
        if len(videos) == 1:
            await message.answer_video(video=videos[0].id_file)
        else:
            media = [InputMediaVideo(media=a.id_file) for a in videos]
            await message.bot.send_media_group(chat_id=message.chat.id, media=media)

    # Остальные файлы по одному
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