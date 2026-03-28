"""
Хендлеры: список чатов, создание, заморозка, выход.
ЗАДАЧА 6: переключение режима компании.
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
    main_menu_keyboard, chats_list_keyboard, chat_detail_keyboard,
    delete_chat_confirm_keyboard, freeze_confirm_keyboard,
    leave_confirm_keyboard, cancel_keyboard,
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
    sent = await call.message.edit_text("✏️ Введите название нового чата:", reply_markup=cancel_keyboard())
    await state.update_data(prompt_msg_id=sent.message_id if sent else call.message.message_id)
    await call.answer()


@router.message(ChatCreateState.get_title, CheckUser())
async def fsm_chat_title(message: types.Message, state: FSMContext, **_):
    data = await state.get_data()
    await state.update_data(title=message.text.strip())
    await state.set_state(ChatCreateState.get_description)

    try:
        await message.delete()
    except Exception:
        pass

    prompt_msg_id = data.get('prompt_msg_id')
    if prompt_msg_id:
        try:
            sent = await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=prompt_msg_id,
                text="📝 Введите описание чата (или отправьте «-» чтобы пропустить):",
                reply_markup=cancel_keyboard(),
            )
            await state.update_data(prompt_msg_id=sent.message_id)
            return
        except Exception:
            pass

    sent = await message.answer(
        "📝 Введите описание чата (или отправьте «-» чтобы пропустить):",
        reply_markup=cancel_keyboard(),
    )
    await state.update_data(prompt_msg_id=sent.message_id)


@router.message(ChatCreateState.get_description, CheckUser())
async def fsm_chat_description(message: types.Message, state: FSMContext, **_):
    description = message.text.strip()
    if description == '-':
        description = None
    await state.update_data(description=description)
    await state.set_state(ChatCreateState.get_admin_description)

    try:
        await message.delete()
    except Exception:
        pass

    data = await state.get_data()
    prompt_msg_id = data.get('prompt_msg_id')
    if prompt_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=prompt_msg_id,
                text="🔒 Введите <b>приватное</b> описание чата (только для администраторов).\n\n"
                     "Или отправьте «-» чтобы пропустить:",
                reply_markup=cancel_keyboard(),
                parse_mode="HTML",
            )
            return
        except Exception:
            pass

    sent = await message.answer(
        "🔒 Введите <b>приватное</b> описание чата (только для администраторов).\n\n"
        "Или отправьте «-» чтобы пропустить:",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML",
    )
    await state.update_data(prompt_msg_id=sent.message_id)


@router.message(ChatCreateState.get_admin_description, CheckUser())
async def fsm_chat_admin_description(message: types.Message, state: FSMContext, **_):
    admin_description = message.text.strip()
    if admin_description == '-':
        admin_description = None
    await state.update_data(admin_description=admin_description)
    await state.set_state(ChatCreateState.get_filters)

    try:
        await message.delete()
    except Exception:
        pass

    data = await state.get_data()
    prompt_msg_id = data.get('prompt_msg_id')
    if prompt_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=prompt_msg_id,
                text="🚫 Введите regex фильтры для чата (каждая строка — отдельный).\n\n"
                     "Или отправьте «-» чтобы пропустить:",
                reply_markup=cancel_keyboard(),
            )
            return
        except Exception:
            pass

    sent = await message.answer(
        "🚫 Введите regex фильтры для чата (каждая строка — отдельный).\n\n"
        "Или отправьте «-» чтобы пропустить:",
        reply_markup=cancel_keyboard(),
    )
    await state.update_data(prompt_msg_id=sent.message_id)


@router.message(ChatCreateState.get_filters, CheckUser())
async def fsm_chat_filters(
    message: types.Message,
    state: FSMContext,
    user: models.UserTelegram,
    profile: models.Profile | None = None,
):
    data = await state.get_data()
    raw = message.text.strip()
    await state.clear()

    try:
        await message.delete()
    except Exception:
        pass

    prompt_msg_id = data.get('prompt_msg_id')
    if prompt_msg_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
        except Exception:
            pass

    with models.connector:
        chat = models.Chat.create(
            title=data['title'],
            description=data.get('description'),
            admin_description=data.get('admin_description'),
            creator_id=profile.id if profile else None,
        )

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

        # Фильтры чата
        filter_count = 0
        if raw != '-':
            patterns = [line.strip() for line in raw.splitlines() if line.strip()]
            for p in patterns:
                models.ChatFilter.create(chat_id=chat.id, pattern=p)
            filter_count = len(patterns)

    prefix = f"✅ Чат <b>{chat.title}</b> создан!"
    if filter_count:
        prefix += f"\n🚫 Добавлено фильтров: {filter_count}"

    await show_chats_list(message, user, is_admin_or_manager=True, prefix=prefix)


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
async def cb_freeze_confirm(
    call: types.CallbackQuery,
    callback_data: ChatCD,
    user: models.UserTelegram,
    is_admin_or_manager: bool,
):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    if callback_data.page != 1:
        await show_chat_detail(call, callback_data.chat_id, user, is_admin_or_manager=True)
        await call.answer("Отменено")
        return

    chat_id = callback_data.chat_id
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

    await show_chat_detail(call, chat_id, user, is_admin_or_manager=True, prefix=f"✅ {notify}")
    await call.answer()


# ══════════════════════════════════════════════
#  ЗАДАЧА 6: Переключение режима компании
# ══════════════════════════════════════════════
@router.callback_query(ChatCD.filter(F.action == ChatAction.toggle_company_mode), CheckUser())
async def cb_toggle_company_mode(
    call: types.CallbackQuery,
    callback_data: ChatCD,
    user: models.UserTelegram,
    is_admin_or_manager: bool,
):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    chat_id = callback_data.chat_id
    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        if not chat:
            await call.answer("Чат не найден", show_alert=True)
            return
        chat.company_mode = not chat.company_mode
        chat.save()
        new_mode = chat.company_mode

    mode_text = "включён 🏢" if new_mode else "выключен 👤"
    await show_chat_detail(
        call, chat_id, user, is_admin_or_manager=True,
        prefix=f"✅ Режим компании {mode_text}."
    )
    await call.answer()


# ══════════════════════════════════════════════
#  Выйти из чата
# ══════════════════════════════════════════════
@router.callback_query(ChatCD.filter(F.action == ChatAction.leave), CheckUser())
async def cb_leave_ask(
    call: types.CallbackQuery,
    callback_data: ChatCD,
    user: models.UserTelegram,
    is_admin_or_manager: bool,
):
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
async def cb_leave_confirm(
    call: types.CallbackQuery,
    callback_data: ChatCD,
    user: models.UserTelegram,
    is_admin_or_manager: bool,
):
    confirmed = callback_data.page == 1
    if not confirmed:
        await show_chat_detail(call, callback_data.chat_id, user, is_admin_or_manager=False)
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
        tg_user = call.from_user
        name = tg_user.full_name or str(tg_user.id)
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
async def cb_chat_back(
    call: types.CallbackQuery,
    callback_data: ChatCD,
    user: models.UserTelegram,
    profile: models.Profile | None,
    is_admin_or_manager: bool,
):
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
async def cb_delete_chat_confirm(
    call: types.CallbackQuery,
    callback_data: ChatCD,
    user: models.UserTelegram,
    is_admin_or_manager: bool,
):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    if callback_data.page != 1:
        await show_chat_detail(call, callback_data.chat_id, user, is_admin_or_manager=True)
        await call.answer("Отменено")
        return

    chat_id = callback_data.chat_id

    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        if not chat:
            await call.answer("Чат не найден", show_alert=True)
            return

        chat_title = chat.title

        members = list(models.ChatMember.select().where(
            models.ChatMember.chat_id == chat_id
        ))

        chat.delete_instance(recursive=True)

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

    await show_chats_list(call, user, is_admin_or_manager=True,
                          prefix=f"✅ Чат <b>{chat_title}</b> удалён.")
    await call.answer()


@router.callback_query(ChatCD.filter(F.action == ChatAction.join), CheckUser())
async def cb_join_chat(
    call: types.CallbackQuery,
    callback_data: ChatCD,
    user: models.UserTelegram,
    profile: models.Profile | None,
    is_admin_or_manager: bool,
):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    chat_id = callback_data.chat_id

    with models.connector:
        existing = models.ChatMember.get_or_none(
            (models.ChatMember.user_id == user.id) &
            (models.ChatMember.chat_id == chat_id)
        )
        if existing:
            await call.answer("Вы уже в этом чате", show_alert=True)
            return

        chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        models.ChatMember.create(
            chat_id=chat_id,
            user_id=user.id,
            profile_id=profile.id if profile else None,
            member_type=models.MemberType.ADMIN if is_admin_or_manager else models.MemberType.EMPLOYEE,
        )

    await show_chat_detail(call, chat_id, user, is_admin_or_manager,
                           prefix=f"✅ Вы присоединились к чату <b>{chat.title}</b>!")
    await call.answer()