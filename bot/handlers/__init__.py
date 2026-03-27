"""
Переиспользуемые функции рендера экранов.
Задача 11: счётчик непрочитанных в списке чатов.
Задача 4: МСК часовой пояс.
"""
import config
import models
from aiogram.exceptions import TelegramBadRequest
from aiogram import types
from keyboards.kb import (
    chat_detail_keyboard,
    chats_list_keyboard,
    members_list_keyboard,
    member_detail_keyboard,
    staff_list_keyboard,
    staff_detail_keyboard,
    history_keyboard,
)


def _msk_dt(dt) -> str:
    """Форматирует datetime в строку МСК."""
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        import pytz
        dt = pytz.utc.localize(dt).astimezone(config.TIMEZONE)
    else:
        dt = dt.astimezone(config.TIMEZONE)
    return dt.strftime("%d.%m.%Y %H:%M")


# ══════════════════════════════════════════════
#  Чаты
# ══════════════════════════════════════════════

async def show_chats_list(
    target: types.Message | types.CallbackQuery,
    user: models.UserTelegram,
    is_admin_or_manager: bool,
    page: int = 0,
    prefix: str = "",
):
    with models.connector:
        if is_admin_or_manager:
            chats = list(models.Chat.select().where(models.Chat.is_visible == True))
        else:
            memberships = list(
                models.ChatMember.select().where(
                    (models.ChatMember.user_id == user.id) &
                    (models.ChatMember.is_blocked == False)
                )
            )
            chat_ids = [m.chat_id_id for m in memberships]
            chats = list(models.Chat.select().where(
                (models.Chat.id.in_(chat_ids)) & (models.Chat.is_visible == True)
            )) if chat_ids else []

        # Задача 11: собираем непрочитанные для каждого чата
        member_map: dict[int, models.ChatMember] = {}
        read_map: dict[int, int] = {}  # member_id -> last_read_message_id
        unread_map: dict[int, int] = {}  # chat_id -> unread count

        for chat in chats:
            m = models.ChatMember.get_or_none(
                (models.ChatMember.user_id == user.id) &
                (models.ChatMember.chat_id == chat.id)
            )
            if m:
                member_map[chat.id] = m
                read_mark = models.MessageRead.get_or_none(
                    models.MessageRead.member_id == m.id
                )
                last_read = read_mark.last_read_message_id if read_mark else 0
                unread = (
                    models.Message.select()
                    .join(models.ChatMember)
                    .where(
                        (models.ChatMember.chat_id == chat.id) &
                        (models.Message.id > last_read)
                    )
                    .count()
                )
                unread_map[chat.id] = unread

    if not chats:
        text = "💬 Чатов пока нет."
        if is_admin_or_manager:
            text += "\n\nНажмите «Создать чат» чтобы начать."
    else:
        text = f"💬 <b>Чаты</b> ({len(chats)})"

    if prefix:
        text = f"{prefix}\n\n{text}"

    kb = chats_list_keyboard(chats, page=page, can_create=is_admin_or_manager,
                             unread_map=unread_map)

    msg = target if isinstance(target, types.Message) else target.message
    if isinstance(target, types.CallbackQuery):
        await msg.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await msg.answer(text, reply_markup=kb, parse_mode="HTML")


async def show_chat_detail(
    target: types.Message | types.CallbackQuery,
    chat_id: int,
    user: models.UserTelegram,
    is_admin_or_manager: bool,
    prefix: str = "",
):
    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        if not chat:
            _msg = target.message if isinstance(target, types.CallbackQuery) else target
            await _msg.answer("Чат не найден.")
            return

        members_count = models.ChatMember.select().where(
            models.ChatMember.chat_id == chat_id
        ).count()

    member_is_admin = is_admin_or_manager

    is_member = False
    with models.connector:
        m = models.ChatMember.get_or_none(
            (models.ChatMember.user_id == user.id) &
            (models.ChatMember.chat_id == chat_id)
        )
        if m:
            is_member = True
            member_is_admin = m.is_admin_or_manager

    # Если is_admin_or_manager по профилю — оставляем True
    if is_admin_or_manager:
        member_is_admin = True

    status = "❄️ Заморожен" if chat.is_frozen else "✅ Активен"
    text = (
        f"💬 <b>{chat.title}</b>\n\n"
        f"📊 Статус: {status}\n"
        f"👥 Участников: {members_count}\n"
    )

    if chat.description:
        text += f"\n📝 {chat.description}"

    if member_is_admin and chat.admin_description:
        text += f"\n\n🔒 <i>(Приватно)</i> {chat.admin_description}"

    if prefix:
        text = f"{prefix}\n\n{text}"

    kb = chat_detail_keyboard(chat_id, chat.is_frozen, member_is_admin, is_member=is_member)

    msg = target.message if isinstance(target, types.CallbackQuery) else target
    if isinstance(target, types.CallbackQuery):
        await msg.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await msg.answer(text, reply_markup=kb, parse_mode="HTML")


# ══════════════════════════════════════════════
#  Участники
# ══════════════════════════════════════════════

async def show_members_list(
    target: types.Message | types.CallbackQuery,
    chat_id: int,
    page: int = 0,
    prefix: str = "",
):
    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        members = list(
            models.ChatMember.select()
            .where(models.ChatMember.chat_id == chat_id)
            .order_by(models.ChatMember.date_create)
        )

    text = f"👥 <b>Участники чата «{chat.title if chat else chat_id}»</b> ({len(members)})"
    if prefix:
        text = f"{prefix}\n\n{text}"

    kb = members_list_keyboard(members, chat_id, page)
    msg = target.message if isinstance(target, types.CallbackQuery) else target
    if isinstance(target, types.CallbackQuery):
        await msg.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await msg.answer(text, reply_markup=kb, parse_mode="HTML")


async def show_member_detail(
    target: types.Message | types.CallbackQuery,
    chat_id: int,
    member_id: int,
    prefix: str = "",
):
    with models.connector:
        member = models.ChatMember.get_or_none(models.ChatMember.id == member_id)
        if not member:
            _msg = target.message if isinstance(target, types.CallbackQuery) else target
            await _msg.answer("Участник не найден.")
            return

        real_name = member._real_name
        alias = member.alias
        display = member.display_name

        profile_info = "—"
        if member.profile_id_id:
            p = member.profile_id
            profile_info = f"{p.name} ({p.type_label})"
            if p.position:
                profile_info += f", {p.position}"

        company_info = "—"
        if member.company_id_id:
            try:
                c = member.company_id
                company_info = f"{c.name}" + (" 🔒" if c.is_blocked else "")
            except Exception:
                pass

        messages_count = models.Message.select().where(
            models.Message.member_id == member_id
        ).count()

    status = "🔒 Заморожен" if member.is_blocked else "✅ Активен"

    if alias:
        name_block = (
            f"🏷 Тег (публичное): <b>{alias}</b>\n"
            f"👤 Реальное имя: {real_name}\n"
        )
    else:
        name_block = f"👤 <b>{real_name}</b>\n"

    text = (
        f"{name_block}\n"
        f"📊 Статус: {status}\n"
        f"🏷 Роль: {member.type_label}\n"
        f"👤 Профиль: {profile_info}\n"
        f"🏢 Компания: {company_info}\n"
        f"💬 Сообщений: {messages_count}\n"
    )

    if prefix:
        text = f"{prefix}\n\n{text}"

    kb = member_detail_keyboard(chat_id, member_id, member.is_blocked, has_alias=bool(alias))
    msg = target.message if isinstance(target, types.CallbackQuery) else target
    if isinstance(target, types.CallbackQuery):
        await msg.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await msg.answer(text, reply_markup=kb, parse_mode="HTML")


# ══════════════════════════════════════════════
#  Сотрудники
# ══════════════════════════════════════════════

async def show_staff_list(
    target: types.Message | types.CallbackQuery,
    page: int = 0,
    prefix: str = "",
):
    with models.connector:
        profiles = list(models.Profile.select().order_by(models.Profile.date_create))

    text = f"👥 <b>Сотрудники</b> ({len(profiles)})"
    if prefix:
        text = f"{prefix}\n\n{text}"

    kb = staff_list_keyboard(profiles, page)
    msg = target.message if isinstance(target, types.CallbackQuery) else target
    if isinstance(target, types.CallbackQuery):
        await msg.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await msg.answer(text, reply_markup=kb, parse_mode="HTML")


async def safe_edit(message: types.Message, text: str, reply_markup=None, parse_mode="HTML"):
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest:
        pass


async def show_staff_detail(
    target: types.Message | types.CallbackQuery,
    profile_id: int,
    prefix: str = "",
):
    with models.connector:
        profile = models.Profile.get_or_none(models.Profile.id == profile_id)
        if not profile:
            _msg = target.message if isinstance(target, types.CallbackQuery) else target
            await _msg.answer("Профиль не найден.")
            return

        chats_count = models.ChatMember.select().where(
            models.ChatMember.profile_id == profile_id
        ).count()
        messages_count = (
            models.Message.select()
            .join(models.ChatMember)
            .where(models.ChatMember.profile_id == profile_id)
            .count()
        )

    connected = "✅ Подключён" if profile.user_id_id else "❌ Не подключён"
    blocked = "🔒 Заблокирован" if profile.is_blocked else "✅ Активен"

    text = (
        f"👤 <b>{profile.name}</b>\n\n"
        f"🏷 Роль: {profile.type_label}\n"
        f"💼 Должность: {profile.position or '—'}\n"
        f"📊 Статус: {blocked}\n"
        f"🔗 Telegram: {connected}\n"
        f"💬 Чатов: {chats_count}\n"
        f"📝 Сообщений: {messages_count}\n"
    )
    if not profile.user_id_id:
        link = f"https://t.me/{config.BOT_USERNAME}?start=pe_{profile.connect_token}"
        text += f"\n🔗 Ссылка для подключения:\n<code>{link}</code>"

    if prefix:
        text = f"{prefix}\n\n{text}"

    kb = staff_detail_keyboard(profile_id)
    msg = target.message if isinstance(target, types.CallbackQuery) else target
    if isinstance(target, types.CallbackQuery):
        await safe_edit(msg, text, reply_markup=kb)
    else:
        await msg.answer(text, reply_markup=kb, parse_mode="HTML")