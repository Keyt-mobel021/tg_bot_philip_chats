"""
/start хендлер — точка входа, диплинки, Reply-кнопка меню, подключение профилей.
Задача 3: welcome text из базы данных (модель BotText, тип 'rules'),
          fallback на text_templates.WELCOME_TEXT.
"""
import datetime
from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from loguru import logger
from filters import *

import models
import text_templates
from keyboards import *
from keyboards.kb import (
    main_menu_keyboard, chat_description_keyboard, cancel_keyboard,
    menu_reply_keyboard,
)
from states import ChatEditState

router = Router()


def _get_welcome_text() -> str:
    """
    Задача 3: возвращает текст правил из БД (модель BotText, тип 'rules').
    Если записи нет — возвращает базовый WELCOME_TEXT из text_templates.
    """
    try:
        with models.connector:
            bot_text = models.BotText.get_or_none(
                (models.BotText.text_type == models.BotTextType.RULES) &
                (models.BotText.is_active == True)
            )
        if bot_text:
            return bot_text.content
    except Exception as e:
        logger.warning(f"_get_welcome_text: {e}")
    return text_templates.WELCOME_TEXT


# ══════════════════════════════════════════════
#  Постоянная Reply-кнопка «Меню»
# ══════════════════════════════════════════════

@router.message(F.text == text_templates.MENU_BUTTON_TEXT, CheckUser())
async def cmd_menu_button(
    message: types.Message,
    state: FSMContext,
    user: models.UserTelegram,
    profile: models.Profile | None,
    is_admin_or_manager: bool,
):
    await state.clear()
    is_adm = is_admin_or_manager or user.is_admin
    await message.answer(
        text_templates.MENU_REPLY_HINT,
        reply_markup=main_menu_keyboard(is_admin_or_manager=is_adm),
    )


# ══════════════════════════════════════════════
#  Кнопка «Домой» из inline-меню
# ══════════════════════════════════════════════

@router.callback_query(MainMenuCD.filter(F.action == MainMenuAction.home), CheckUser())
async def cb_home(
    call: types.CallbackQuery,
    user: models.UserTelegram,
    profile: models.Profile | None,
    is_admin_or_manager: bool,
):
    is_adm = is_admin_or_manager or user.is_admin
    await call.message.edit_text(
        "🏠 Главное меню. Выберите действие:",
        reply_markup=main_menu_keyboard(is_admin_or_manager=is_adm),
    )
    await call.answer()


# ══════════════════════════════════════════════
#  /start
# ══════════════════════════════════════════════

@router.message(CommandStart(), CheckUser())
async def cmd_start(message: types.Message, state: FSMContext, user: models.UserTelegram):
    await state.clear()

    tg = message.from_user
    args = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""

    welcome_text = _get_welcome_text()

    # ── Диплинк: подключить профиль сотрудника ──────────────
    if args.startswith("pe_"):
        token = args[3:]
        with models.connector:
            profile = models.Profile.get_or_none(models.Profile.connect_token == token)

        if not profile:
            await message.answer("❌ Ссылка недействительна или уже была использована.")
            return

        with models.connector:
            if profile.user_id_id and profile.user_id_id != tg.id:
                await message.answer("❌ Этот профиль уже подключён к другому аккаунту.")
                return

            profile.user_id_id = tg.id
            profile.save()

        logger.info(f"Profile {profile.id} ({profile.name}) connected to user {tg.id}")

        await message.answer(
            welcome_text,
            parse_mode="HTML",
            reply_markup=menu_reply_keyboard(),
        )
        await message.answer(
            f"✅ Вы подключены как <b>{profile.name}</b> ({profile.type_label}).\n\n"
            f"Добро пожаловать!",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin_or_manager=profile.is_admin_or_manager),
        )
        return

    # ── Диплинк con_ — многоразовая ссылка на чат ──
    if args.startswith("con_"):
        token = args[4:]
        with models.connector:
            chat_invite = models.ChatInviteLink.get_or_none(
                models.ChatInviteLink.token == token
            )

        if not chat_invite:
            with models.connector:
                member = models.ChatMember.get_or_none(
                    models.ChatMember.connect_token == token
                )

            if not member:
                await message.answer("❌ Ссылка недействительна.")
                return

            with models.connector:
                if member.user_id_id and member.user_id_id != tg.id:
                    await message.answer("❌ Эта ссылка уже была использована другим пользователем.")
                    return

                member.user_id_id = tg.id
                profile = models.Profile.get_or_none(models.Profile.user_id == tg.id)
                if profile:
                    member.profile_id_id = profile.id
                member.save()
                chat = models.Chat.get_or_none(models.Chat.id == member.chat_id_id)

            chat_name = chat.title if chat else "чат"
            is_adm = profile.is_admin_or_manager if profile else False
            await message.answer(
                welcome_text,
                parse_mode="HTML",
                reply_markup=menu_reply_keyboard(),
            )
            await message.answer(
                f"✅ Вы подключены к чату <b>{chat_name}</b>!\n\n"
                f"Нажмите «Чаты» чтобы начать общение.",
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(is_admin_or_manager=is_adm),
            )
            return

        # ── Многоразовая ссылка ──────────────────────────────
        with models.connector:
            chat = models.Chat.get_or_none(models.Chat.id == chat_invite.chat_id_id)
            if not chat or not chat.is_visible:
                await message.answer("❌ Чат не найден или недоступен.")
                return

            existing_member = models.ChatMember.get_or_none(
                (models.ChatMember.chat_id == chat.id) &
                (models.ChatMember.user_id == tg.id)
            )
            if existing_member:
                profile_check = models.Profile.get_or_none(models.Profile.user_id == tg.id)
                is_adm = profile_check.is_admin_or_manager if profile_check else False
                await message.answer(
                    f"ℹ️ Вы уже состоите в чате <b>{chat.title}</b>.",
                    parse_mode="HTML",
                    reply_markup=main_menu_keyboard(is_admin_or_manager=is_adm),
                )
                return

            profile = models.Profile.get_or_none(models.Profile.user_id == tg.id)

            if profile:
                member_type = models.MemberType.ADMIN if profile.is_admin_or_manager else models.MemberType.EMPLOYEE
                models.ChatMember.create(
                    chat_id=chat.id,
                    user_id=tg.id,
                    profile_id=profile.id,
                    member_type=member_type,
                )
                is_adm = profile.is_admin_or_manager
            else:
                models.ChatMember.create(
                    chat_id=chat.id,
                    user_id=tg.id,
                    member_type=models.MemberType.CLIENT,
                )
                is_adm = False

        logger.info(f"User {tg.id} joined chat {chat.id} via multi-use invite link {token}")

        await message.answer(
            welcome_text,
            parse_mode="HTML",
            reply_markup=menu_reply_keyboard(),
        )
        await message.answer(
            f"✅ Вы подключены к чату <b>{chat.title}</b>!\n\n"
            f"Нажмите «Чаты» чтобы начать общение.",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin_or_manager=is_adm),
        )
        return

    # ── Диплинк media_<chat_id>_<message_id> ────
    if args.startswith("media_"):
        try:
            await message.delete()
        except Exception:
            pass

        parts = args[6:].split("_", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            message_id = int(parts[1])
            from handlers.chat_messages import send_message_media
            await send_message_media(message, message_id, user)
        else:
            await message.answer("❌ Некорректная ссылка на медиа.")
        return

    # ── Обычный старт ────────────────────────────────────────
    with models.connector:
        profile = models.Profile.get_or_none(models.Profile.user_id == tg.id)

    is_adm = (profile and profile.is_admin_or_manager) or user.is_admin

    await message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=menu_reply_keyboard(),
    )

    greeting = f"👋 Привет, <b>{tg.full_name or 'пользователь'}</b>!\n\n"
    if profile:
        greeting += f"Вы вошли как: <b>{profile.name}</b> ({profile.type_label})\n\n"
    greeting += "Выберите действие:"

    await message.answer(
        greeting,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin_or_manager=is_adm),
    )


# ══════════════════════════════════════════════
#  Переименование чата
# ══════════════════════════════════════════════

@router.callback_query(ChatCD.filter(F.action == ChatAction.rename), CheckUser())
async def cb_rename_chat(
    call: types.CallbackQuery,
    callback_data: ChatCD,
    state: FSMContext,
    is_admin_or_manager: bool,
):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(ChatEditState.get_title)
    await state.update_data(chat_id=callback_data.chat_id)
    await call.message.edit_text(
        "✏️ Введите новое название чата:",
        reply_markup=cancel_keyboard(),
    )
    await call.answer()


@router.message(ChatEditState.get_title, CheckUser())
async def fsm_rename_chat(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data["chat_id"]
    new_title = message.text.strip()
    await state.clear()

    try:
        await message.delete()
    except Exception:
        pass

    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        if chat:
            chat.title = new_title
            chat.save()

    from handlers import show_chat_detail
    from models import UserTelegram
    with models.connector:
        user = UserTelegram.get_or_none(UserTelegram.id == message.from_user.id)

    await show_chat_detail(message, chat_id, user, is_admin_or_manager=True,
                           prefix=f"✅ Чат переименован в <b>{new_title}</b>.")


# ══════════════════════════════════════════════
#  Просмотр и редактирование описания чата
# ══════════════════════════════════════════════

@router.callback_query(ChatCD.filter(F.action == ChatAction.description), CheckUser())
async def cb_chat_description(
    call: types.CallbackQuery,
    callback_data: ChatCD,
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

    pub_desc = chat.description or "<i>Не задано</i>"
    adm_desc = chat.admin_description or "<i>Не задано</i>"

    text = (
        f"📝 <b>Описание чата «{chat.title}»</b>\n\n"
        f"🌐 <b>Общее</b> (видят все участники):\n{pub_desc}\n\n"
        f"🔒 <b>Приватное</b> (только для администраторов):\n{adm_desc}"
    )

    await call.message.edit_text(
        text,
        reply_markup=chat_description_keyboard(chat_id),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(ChatCD.filter(F.action == ChatAction.edit_description), CheckUser())
async def cb_edit_description_start(
    call: types.CallbackQuery,
    callback_data: ChatCD,
    state: FSMContext,
    is_admin_or_manager: bool,
):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(ChatEditState.get_description)
    await state.update_data(chat_id=callback_data.chat_id)
    await call.message.edit_text(
        "📝 Введите новое <b>общее</b> описание чата\n(или «-» чтобы очистить):",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()


@router.message(ChatEditState.get_description, CheckUser())
async def fsm_edit_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data["chat_id"]
    await state.clear()

    description = message.text.strip()
    if description == "-":
        description = None

    try:
        await message.delete()
    except Exception:
        pass

    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        if chat:
            chat.description = description
            chat.save()

    pub_desc = description or "<i>Не задано</i>"
    with models.connector:
        adm_desc = (chat.admin_description or "<i>Не задано</i>") if chat else "<i>Не задано</i>"

    await message.answer(
        f"✅ Общее описание обновлено.\n\n"
        f"📝 <b>Описание чата «{chat.title if chat else chat_id}»</b>\n\n"
        f"🌐 <b>Общее:</b>\n{pub_desc}\n\n"
        f"🔒 <b>Приватное:</b>\n{adm_desc}",
        reply_markup=chat_description_keyboard(chat_id),
        parse_mode="HTML",
    )


@router.callback_query(ChatCD.filter(F.action == ChatAction.edit_admin_description), CheckUser())
async def cb_edit_admin_description_start(
    call: types.CallbackQuery,
    callback_data: ChatCD,
    state: FSMContext,
    is_admin_or_manager: bool,
):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(ChatEditState.get_admin_description)
    await state.update_data(chat_id=callback_data.chat_id)
    await call.message.edit_text(
        "🔒 Введите <b>приватное</b> описание чата\n(или «-» чтобы очистить):",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()


@router.message(ChatEditState.get_admin_description, CheckUser())
async def fsm_edit_admin_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data["chat_id"]
    await state.clear()

    description = message.text.strip()
    if description == "-":
        description = None

    try:
        await message.delete()
    except Exception:
        pass

    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        if chat:
            chat.admin_description = description
            chat.save()

    adm_desc = description or "<i>Не задано</i>"
    with models.connector:
        pub_desc = (chat.description or "<i>Не задано</i>") if chat else "<i>Не задано</i>"

    await message.answer(
        f"✅ Приватное описание обновлено.\n\n"
        f"📝 <b>Описание чата «{chat.title if chat else chat_id}»</b>\n\n"
        f"🌐 <b>Общее:</b>\n{pub_desc}\n\n"
        f"🔒 <b>Приватное:</b>\n{adm_desc}",
        reply_markup=chat_description_keyboard(chat_id),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════
#  Отмена любого FSM
# ══════════════════════════════════════════════

@router.callback_query(F.data == "cancel")
async def cb_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    tg = call.from_user

    with models.connector:
        tg_user = models.UserTelegram.get_or_none(models.UserTelegram.id == tg.id)
        profile = models.Profile.get_or_none(models.Profile.user_id == tg.id)

    is_adm = (profile and profile.is_admin_or_manager) or (tg_user and tg_user.is_admin)

    await call.message.edit_text(
        "❌ Отменено. Выберите действие:",
        reply_markup=main_menu_keyboard(is_admin_or_manager=is_adm),
    )
    await call.answer()