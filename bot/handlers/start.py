"""
/start хендлер — точка входа, диплинки, подключение профилей и чатов.
"""
import datetime
from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from loguru import logger
from filters import *

import models
from keyboards import *
from keyboards.kb import main_menu_keyboard, chat_description_keyboard, cancel_keyboard
from states import ChatDescriptionEditState

router = Router()


@router.callback_query(MainMenuCD.filter(F.action == MainMenuAction.home), CheckUser())
async def cb_home(call: types.CallbackQuery, user: models.UserTelegram, profile: models.Profile | None, is_admin_or_manager: bool):
    is_adm = is_admin_or_manager or user.is_admin
    await call.message.edit_text(
        "🏠 Главное меню. Выберите действие:",
        reply_markup=main_menu_keyboard(is_admin_or_manager=is_adm),
    )
    await call.answer()


@router.message(CommandStart(), CheckUser())
async def cmd_start(message: types.Message, state: FSMContext, user: models.UserTelegram):
    await state.clear()
    tg = message.from_user
    args = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""

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
            f"✅ Вы подключены как <b>{profile.name}</b> ({profile.type_label}).\n\n"
            f"Добро пожаловать!",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin_or_manager=profile.is_admin_or_manager),
        )
        return

    # ── ЗАДАЧА 4: Диплинк con_ — многоразовая ссылка на чат ──
    if args.startswith("con_"):
        token = args[4:]
        with models.connector:
            chat_invite = models.ChatInviteLink.get_or_none(
                models.ChatInviteLink.token == token
            )

        if not chat_invite:
            # Обратная совместимость: старые одноразовые ссылки на ChatMember
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

            # Проверяем, не состоит ли пользователь уже в чате
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

            # Ищем профиль пользователя
            profile = models.Profile.get_or_none(models.Profile.user_id == tg.id)

            if profile:
                # Есть профиль — подключаем как сотрудника
                member_type = models.MemberType.ADMIN if profile.is_admin_or_manager else models.MemberType.EMPLOYEE
                models.ChatMember.create(
                    chat_id=chat.id,
                    user_id=tg.id,
                    profile_id=profile.id,
                    member_type=member_type,
                )
                is_adm = profile.is_admin_or_manager
            else:
                # Нет профиля — подключаем как клиента (только telegram-аккаунт)
                models.ChatMember.create(
                    chat_id=chat.id,
                    user_id=tg.id,
                    member_type=models.MemberType.CLIENT,
                )
                is_adm = False

        logger.info(f"User {tg.id} joined chat {chat.id} via multi-use invite link {token}")

        await message.answer(
            f"✅ Вы подключены к чату <b>{chat.title}</b>!\n\n"
            f"Нажмите «Чаты» чтобы начать общение.",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(is_admin_or_manager=is_adm),
        )
        return

    # ── ЗАДАЧА 2б: Диплинк media_<chat_id>_<message_id> ────
    if args.startswith("media_"):
        parts = args[6:].split("_", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            chat_id = int(parts[0])
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

    greeting = f"👋 Привет, <b>{tg.first_name}</b>!\n\n"
    if profile:
        greeting += f"Вы вошли как: <b>{profile.name}</b> ({profile.type_label})\n\n"

    greeting += "Выберите действие:"

    await message.answer(
        greeting,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin_or_manager=is_adm),
    )


# ══════════════════════════════════════════════
#  ЗАДАЧА 5: Просмотр и редактирование описания чата (только для админов)
# ══════════════════════════════════════════════

@router.callback_query(ChatCD.filter(F.action == ChatAction.description), CheckUser())
async def cb_chat_description(call: types.CallbackQuery, callback_data: ChatCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    chat_id = callback_data.chat_id
    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)

    if not chat:
        await call.answer("Чат не найден", show_alert=True)
        return

    desc_text = chat.description or "<i>Описание не задано</i>"
    text = (
        f"📝 <b>Описание чата «{chat.title}»</b>\n\n"
        f"{desc_text}"
    )

    await call.message.edit_text(
        text,
        reply_markup=chat_description_keyboard(chat_id),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(ChatCD.filter(F.action == ChatAction.edit_description), CheckUser())
async def cb_edit_description_start(call: types.CallbackQuery, callback_data: ChatCD, state: FSMContext, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(ChatDescriptionEditState.get_description)
    await state.update_data(chat_id=callback_data.chat_id)
    await call.message.edit_text(
        "📝 Введите новое описание чата (или «-» чтобы очистить):",
        reply_markup=cancel_keyboard(),
    )
    await call.answer()


@router.message(ChatDescriptionEditState.get_description, CheckUser())
async def fsm_edit_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data["chat_id"]
    await state.clear()

    description = message.text.strip()
    if description == "-":
        description = None

    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        if chat:
            chat.description = description
            chat.save()

    desc_text = description or "<i>Описание не задано</i>"
    await message.answer(
        f"✅ Описание обновлено.\n\n"
        f"📝 <b>Описание чата «{chat.title if chat else chat_id}»</b>\n\n"
        f"{desc_text}",
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