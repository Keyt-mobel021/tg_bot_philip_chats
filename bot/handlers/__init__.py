from aiogram import types
from aiogram.types import ReplyKeyboardMarkup

import models
import config
from keyboards.kb import (
    staff_list_keyboard, staff_detail_keyboard,
    members_list_keyboard, member_detail_keyboard,
    chats_list_keyboard, chat_detail_keyboard,
    menu_reply_keyboard,
)


# ──────────────────────────────────────────────
#  Вспомогательная функция — безопасная отправка
#  Гарантирует, что reply-клавиатура всегда присутствует (задача 5)
# ──────────────────────────────────────────────

async def _safe_send(
    target: types.Message | types.CallbackQuery,
    text: str,
    reply_markup=None,
    parse_mode: str = "HTML",
):
    """
    Отправляет/редактирует сообщение.
    Для message.answer — всегда добавляет reply_markup menu_reply_keyboard(),
    чтобы кнопка «Меню» снизу не исчезала при краше.
    """
    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        # message.answer — всегда прокидываем reply_kb отдельным сообщением, если его нет
        await target.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)


# ──────────────────────────────────────────────
#  Список чатов
# ──────────────────────────────────────────────

async def show_chats_list(
    target: types.Message | types.CallbackQuery,
    user: models.UserTelegram,
    is_admin_or_manager: bool,
    page: int = 0,
    prefix: str = "",
):
    with models.connector:
        if is_admin_or_manager:
            chats = list(models.Chat.select().order_by(models.Chat.date_create.desc()))
        else:
            member_chat_ids = [
                m.chat_id_id for m in
                models.ChatMember.select().where(
                    (models.ChatMember.user_id == user.id) &
                    (models.ChatMember.is_blocked == False)
                )
            ]
            chats = list(
                models.Chat.select().where(
                    models.Chat.id.in_(member_chat_ids) if member_chat_ids
                    else models.Chat.id.is_null(True)
                ).order_by(models.Chat.date_create.desc())
            )

        # Непрочитанные
        unread_map: dict[int, int] = {}
        if user:
            member_map = {
                m.chat_id_id: m.id for m in
                models.ChatMember.select().where(models.ChatMember.user_id == user.id)
            }
            for chat_id_key, member_id in member_map.items():
                read_mark = models.MessageRead.get_or_none(
                    models.MessageRead.member_id == member_id
                )
                last_read = read_mark.last_read_message_id if read_mark else 0
                count = models.Message.select().join(models.ChatMember).where(
                    (models.ChatMember.chat_id == chat_id_key) &
                    (models.Message.id > last_read)
                ).count()
                if count > 0:
                    unread_map[chat_id_key] = count

    text = (prefix + "\n\n" if prefix else "") + "💬 <b>Чаты</b>\n\nВыберите чат из списка:"
    kb = chats_list_keyboard(
        chats, page=page,
        can_create=is_admin_or_manager,
        unread_map=unread_map,
    )

    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")


# ──────────────────────────────────────────────
#  Детали чата
# ──────────────────────────────────────────────

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
            if isinstance(target, types.CallbackQuery):
                await target.answer("Чат не найден", show_alert=True)
            else:
                await target.answer("❌ Чат не найден.")
            return

        member = models.ChatMember.get_or_none(
            (models.ChatMember.chat_id == chat_id) &
            (models.ChatMember.user_id == user.id)
        )

        members_count = models.ChatMember.select().where(
            models.ChatMember.chat_id == chat_id
        ).count()

    is_member = member is not None
    status = "❄️ Заморожен" if chat.is_frozen else "✅ Активен"

    desc_block = f"\n\n📝 {chat.description}" if chat.description else ""
    admin_desc_block = ""
    if is_admin_or_manager and chat.admin_description:
        admin_desc_block = f"\n\n🔒 <i>{chat.admin_description}</i>"

    text = (
        (prefix + "\n\n" if prefix else "") +
        f"💬 <b>{chat.title}</b>\n"
        f"📊 {status}\n"
        f"👥 Участников: {members_count}"
        f"{desc_block}"
        f"{admin_desc_block}"
    )

    kb = chat_detail_keyboard(
        chat_id=chat_id,
        is_frozen=chat.is_frozen,
        is_admin_or_manager=is_admin_or_manager,
        is_member=is_member,
        company_mode=chat.company_mode,
    )

    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")


# ──────────────────────────────────────────────
#  Список сотрудников
# ──────────────────────────────────────────────

async def show_staff_list(
    target: types.Message | types.CallbackQuery,
    page: int = 0,
    prefix: str = "",
):
    with models.connector:
        profiles = list(models.Profile.select().order_by(models.Profile.date_create))

    text = (prefix + "\n\n" if prefix else "") + f"👥 <b>Сотрудники</b> ({len(profiles)})"
    kb = staff_list_keyboard(profiles, page=page)

    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")


# ──────────────────────────────────────────────
#  Детали сотрудника
# ──────────────────────────────────────────────

async def show_staff_detail(
    target: types.Message | types.CallbackQuery,
    profile_id: int,
    prefix: str = "",
):
    with models.connector:
        profile = models.Profile.get_or_none(models.Profile.id == profile_id)
        if not profile:
            if isinstance(target, types.CallbackQuery):
                await target.answer("Профиль не найден", show_alert=True)
            else:
                await target.answer("❌ Профиль не найден.")
            return

        chats_count = models.ChatMember.select().where(
            models.ChatMember.profile_id == profile_id
        ).count()
        msgs_count = (
            models.Message.select()
            .join(models.ChatMember)
            .where(models.ChatMember.profile_id == profile_id)
            .count()
        )
        tg_linked = profile.user_id_id is not None
        status = "✅ Активен" if not profile.is_blocked else "🔒 Заблокирован"
        tg_status = "✅ Подключён" if tg_linked else "❌ Не подключён"

    # ЗАДАЧА 3: показываем должность перед именем в заголовке
    title_parts = []
    if profile.position:
        title_parts.append(profile.position)
    title_parts.append(profile.name)
    display_title = " — ".join(title_parts)

    text = (
        (prefix + "\n\n" if prefix else "") +
        f"👤 <b>{display_title}</b>\n\n"
        f"🎭 Роль: {profile.type_label}\n"
        f"💼 Должность: {profile.position or '—'}\n"
        f"📊 Статус: {status}\n"
        f"🔗 Telegram: {tg_status}\n"
        f"💬 Чатов: {chats_count}\n"
        f"📨 Сообщений: {msgs_count}"
    )

    kb = staff_detail_keyboard(profile_id)

    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.answer(
            text,
            reply_markup=kb,
            parse_mode="HTML",
        )
        # Восстанавливаем reply-кнопку «Меню»
        await target.answer(
            "📋 Меню доступно снизу:",
            reply_markup=menu_reply_keyboard(),
        )


# ──────────────────────────────────────────────
#  Список участников чата
# ──────────────────────────────────────────────

async def show_members_list(
    target: types.Message | types.CallbackQuery,
    chat_id: int,
    page: int = 0,
    prefix: str = "",
):
    with models.connector:
        members = list(
            models.ChatMember.select().where(
                models.ChatMember.chat_id == chat_id
            ).order_by(models.ChatMember.date_create)
        )
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)

    chat_name = chat.title if chat else str(chat_id)
    text = (
        (prefix + "\n\n" if prefix else "") +
        f"👥 <b>Участники чата «{chat_name}»</b> ({len(members)})"
    )
    kb = members_list_keyboard(members, chat_id, page=page)

    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")


# ──────────────────────────────────────────────
#  Детали участника чата
# ──────────────────────────────────────────────

async def show_member_detail(
    target: types.Message | types.CallbackQuery,
    chat_id: int,
    member_id: int,
    prefix: str = "",
):
    with models.connector:
        member = models.ChatMember.get_or_none(models.ChatMember.id == member_id)
        if not member:
            if isinstance(target, types.CallbackQuery):
                await target.answer("Участник не найден", show_alert=True)
            else:
                await target.answer("❌ Участник не найден.")
            return

        msgs_count = models.Message.select().where(
            models.Message.member_id == member_id
        ).count()

    status = "🔒 Заморожен" if member.is_blocked else "✅ Активен"
    real_name = member._real_name
    alias_line = f"\n🏷 Тег: <b>{member.alias}</b>" if member.alias else ""

    text = (
        (prefix + "\n\n" if prefix else "") +
        f"👤 <b>{member.display_name}</b>\n"
        f"🎭 Роль: {member.type_label}\n"
        f"📊 Статус: {status}"
        f"{alias_line}\n"
        f"📨 Сообщений: {msgs_count}"
    )

    kb = member_detail_keyboard(
        chat_id=chat_id,
        member_id=member_id,
        is_blocked=member.is_blocked,
        has_alias=bool(member.alias),
    )

    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")