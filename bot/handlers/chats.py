"""
Хендлеры: список чатов, создание, заморозка, выход.
"""
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from loguru import logger

import models
from filters import CheckUser
from keyboards import (
    MainMenuCD, MainMenuAction,
    ChatsCD, ChatsAction,
    ChatCD, ChatAction,
)
from keyboards.kb import (
    main_menu_keyboard, chats_list_keyboard, chat_detail_keyboard, delete_chat_confirm_keyboard,
    freeze_confirm_keyboard, leave_confirm_keyboard, cancel_keyboard,
)
from states import ChatCreateState

from . import *

router = Router()


# ══════════════════════════════════════════════
#  Список чатов
# ══════════════════════════════════════════════
@router.callback_query(MainMenuCD.filter(F.action == MainMenuAction.chats), CheckUser())
@router.callback_query(ChatsCD.filter(F.action == ChatsAction.back), CheckUser())
@router.callback_query(ChatsCD.filter(F.action == ChatsAction.page), CheckUser())
async def cb_chats_list(call, callback_data, user, is_admin_or_manager):
    page = getattr(callback_data, 'page', 0)
    await show_chats_list(call, user, is_admin_or_manager, page=page)
    await call.answer()


# ══════════════════════════════════════════════
#  Создание чата
# ══════════════════════════════════════════════
@router.callback_query(ChatsCD.filter(F.action == ChatsAction.create), CheckUser())
async def cb_create_chat_start(call: types.CallbackQuery, state: FSMContext, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(ChatCreateState.get_title)
    await call.message.edit_text("✏️ Введите название нового чата:", reply_markup=cancel_keyboard())
    await call.answer()


@router.message(ChatCreateState.get_title, CheckUser())
async def fsm_chat_title(message: types.Message, state: FSMContext, **_):
    await state.update_data(title=message.text.strip())
    await state.set_state(ChatCreateState.get_description)
    await message.answer(
        "📝 Введите описание чата (или отправьте «-» чтобы пропустить):",
        reply_markup=cancel_keyboard(),
    )


@router.message(ChatCreateState.get_description, CheckUser())
async def fsm_chat_description(message: types.Message, state: FSMContext, user: models.UserTelegram, profile: models.Profile | None = None):
    data = await state.get_data()
    description = message.text.strip()
    if description == '-':
        description = None

    await state.clear()

    with models.connector:
        chat = models.Chat.create(
            title=data['title'],
            description=description,
            creator_id=profile.id if profile else None,
        )

        # Добавляем создателя как участника-администратора
        if profile:
            models.ChatMember.create(
                chat_id=chat.id,
                user_id=user.id,
                profile_id=profile.id,
                member_type=models.MemberType.ADMIN,
            )

        # Автоподключение
        auto_connects = list(models.AutoConnect.select())
        for ac in auto_connects:
            try:
                p = ac.profile_id
                if p.user_id_id and p.user_id_id != user.id:
                    existing = models.ChatMember.get_or_none(
                        (models.ChatMember.chat_id == chat.id) &
                        (models.ChatMember.profile_id == p.id)
                    )
                    if not existing:
                        member_type = models.MemberType.ADMIN if p.is_admin_or_manager else models.MemberType.EMPLOYEE
                        models.ChatMember.create(
                            chat_id=chat.id,
                            user_id=p.user_id_id,
                            profile_id=p.id,
                            member_type=member_type,
                        )
            except Exception as e:
                logger.warning(f"AutoConnect error: {e}")

    await show_chats_list(message, user, is_admin_or_manager=True, prefix=f"✅ Чат <b>{chat.title}</b> создан!")


# ══════════════════════════════════════════════
#  Детали чата
# ══════════════════════════════════════════════
@router.callback_query(ChatsCD.filter(F.action == ChatsAction.select), CheckUser())
async def cb_chat_detail(call, callback_data, user, is_admin_or_manager):
    await show_chat_detail(call, callback_data.chat_id, user, is_admin_or_manager)
    await call.answer()


# ══════════════════════════════════════════════
#  Заморозить / разморозить чат
# ══════════════════════════════════════════════
@router.callback_query(ChatCD.filter(F.action == ChatAction.freeze), CheckUser())
async def cb_freeze_ask(call: types.CallbackQuery, callback_data: ChatCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    chat_id = callback_data.chat_id
    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)

    action_text = "разморозить" if chat and chat.is_frozen else "заморозить"
    await call.message.edit_text(
        f"❓ Вы уверены, что хотите {action_text} чат <b>{chat.title}</b>?",
        reply_markup=freeze_confirm_keyboard(chat_id, chat.is_frozen if chat else False),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(ChatCD.filter(F.action == ChatAction.freeze_confirm), CheckUser())
async def cb_freeze_confirm(call: types.CallbackQuery, callback_data: ChatCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    confirmed = callback_data.page == 1
    chat_id = callback_data.chat_id

    if not confirmed:
        await call.message.delete()
        await call.answer("Отменено")
        return

    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        if not chat:
            await call.answer("Чат не найден", show_alert=True)
            return
        chat.is_frozen = not chat.is_frozen
        chat.save()
        is_frozen = chat.is_frozen

    action_text = "❄️ заморожен" if is_frozen else "🔥 разморожен"
    notify = f"Чат <b>{chat.title}</b> {action_text}."

    with models.connector:
        members = list(models.ChatMember.select().where(
            models.ChatMember.chat_id == chat_id
        ))

    for m in members:
        if m.user_id_id:
            try:
                await call.bot.send_message(
                    m.user_id_id,
                    f"ℹ️ {notify}",
                    parse_mode="HTML",
                )
            except Exception:
                pass

    await show_chat_detail(call, chat_id, prefix=f"✅ {notify}")
    await call.answer()


# ══════════════════════════════════════════════
#  Выйти из чата
# ══════════════════════════════════════════════
@router.callback_query(ChatCD.filter(F.action == ChatAction.leave), CheckUser())
async def cb_leave_ask(call: types.CallbackQuery, callback_data: ChatCD, user: models.UserTelegram, is_admin_or_manager: bool):
    if is_admin_or_manager:
        await call.answer("Администраторы/руководители не могут выходить из чата", show_alert=True)
        return

    chat_id = callback_data.chat_id
    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)

    await call.message.edit_text(
        f"❓ Вы уверены, что хотите выйти из чата <b>{chat.title if chat else chat_id}</b>?",
        reply_markup=leave_confirm_keyboard(chat_id),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(ChatCD.filter(F.action == ChatAction.leave_confirm), CheckUser())
async def cb_leave_confirm(call: types.CallbackQuery, callback_data: ChatCD, user: models.UserTelegram, is_admin_or_manager: bool):
    confirmed = callback_data.page == 1
    if not confirmed:
        await call.message.delete()
        await call.answer("Отменено")
        return

    chat_id = callback_data.chat_id

    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        member = models.ChatMember.get_or_none(
            (models.ChatMember.user_id == user.id) &
            (models.ChatMember.chat_id == chat_id)
        )
        if member:
            member.delete_instance()

    if chat:
        with models.connector:
            admins = list(models.ChatMember.select().where(
                (models.ChatMember.chat_id == chat_id) &
                (models.ChatMember.member_type.in_([
                    models.MemberType.ADMIN, models.MemberType.MANAGER
                ]))
            ))
        user = call.from_user
        name = user.full_name or str(user.id)
        for a in admins:
            if a.user_id_id:
                try:
                    await call.bot.send_message(
                        a.user_id_id,
                        f"ℹ️ <b>{name}</b> вышел из чата <b>{chat.title}</b>.",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass

    await show_chats_list(call, user, is_admin_or_manager, prefix="✅ Вы вышли из чата.")
    await call.answer()


# ══════════════════════════════════════════════
#  Назад к списку чатов
# ══════════════════════════════════════════════
@router.callback_query(ChatCD.filter(F.action == ChatAction.back), CheckUser())
async def cb_chat_back(call: types.CallbackQuery, callback_data: ChatCD, user: models.UserTelegram, profile: models.Profile | None, is_admin_or_manager: bool):
    await show_chats_list(call, user, is_admin_or_manager, page=0)
    await call.answer()





# ══════════════════════════════════════════════
#  Удалить чат
# ══════════════════════════════════════════════
@router.callback_query(ChatCD.filter(F.action == ChatAction.delete), CheckUser())
async def cb_delete_chat_ask(call: types.CallbackQuery, callback_data: ChatCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    chat_id = callback_data.chat_id
    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)

    if not chat:
        await call.answer("Чат не найден", show_alert=True)
        return

    await call.message.edit_text(
        f"🗑 Вы уверены, что хотите удалить чат <b>{chat.title}</b>?\n\n"
        "⚠️ Все сообщения и участники будут удалены. Это действие необратимо.",
        reply_markup=delete_chat_confirm_keyboard(chat_id),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(ChatCD.filter(F.action == ChatAction.delete_confirm), CheckUser())
async def cb_delete_chat_confirm(call: types.CallbackQuery, callback_data: ChatCD, user: models.UserTelegram, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    # page=0 — нажали "Нет"
    if callback_data.page != 1:
        with models.connector:
            chat = models.Chat.get_or_none(models.Chat.id == callback_data.chat_id)
            members_count = models.ChatMember.select().where(
                models.ChatMember.chat_id == callback_data.chat_id
            ).count()

        status = "❄️ Заморожен" if chat and chat.is_frozen else "✅ Активен"
        text = (
            f"💬 <b>{chat.title}</b>\n\n"
            f"📊 Статус: {status}\n"
            f"👥 Участников: {members_count}\n"
        )
        if chat and chat.description:
            text += f"\n📝 {chat.description}"

        await call.message.edit_text(
            text,
            reply_markup=chat_detail_keyboard(callback_data.chat_id, chat.is_frozen if chat else False, True),
            parse_mode="HTML",
        )
        await call.answer("Отменено")
        return

    chat_id = callback_data.chat_id

    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        if not chat:
            await call.answer("Чат не найден", show_alert=True)
            return

        chat_title = chat.title

        # Уведомляем участников перед удалением
        members = list(models.ChatMember.select().where(
            models.ChatMember.chat_id == chat_id
        ))

    for m in members:
        if m.user_id_id and m.user_id_id != call.from_user.id:
            try:
                await call.bot.send_message(
                    m.user_id_id,
                    f"🗑 Чат <b>{chat_title}</b> был удалён.",
                    parse_mode="HTML",
                )
            except Exception:
                pass

    with models.connector:
        chat.delete_instance(recursive=True)  # cascade удалит участников, сообщения, вложения

    # Возвращаемся к списку чатов через show_chats_list если используешь menu_helpers,
    # или напрямую:
    with models.connector:
        all_chats = list(models.Chat.select().where(models.Chat.is_visible == True))

    await call.message.edit_text(
        f"✅ Чат <b>{chat_title}</b> удалён.\n\n"
        f"💬 <b>Чаты</b> ({len(all_chats)})",
        reply_markup=chats_list_keyboard(all_chats, page=0, can_create=True),
        parse_mode="HTML",
    )
    await call.answer()