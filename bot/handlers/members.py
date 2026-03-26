"""
Хендлеры: управление участниками чата.
Включает: добавление, удаление, заморозка, многоразовые ссылки,
          редактирование тега/псевдонима участника (только для администратора).
"""
import secrets
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from loguru import logger

import models
import config
from filters import CheckUser
from keyboards import (
    MembersCD, MembersAction,
    ChatCD, ChatAction,
    ViolationCD, ViolationAction,
)
from . import *
from keyboards.kb import (
    members_list_keyboard, member_detail_keyboard,
    member_freeze_confirm_keyboard, member_remove_confirm_keyboard,
    add_member_keyboard, invite_link_keyboard,
)
from states import MemberAliasState

router = Router()


# ══════════════════════════════════════════════
#  Список участников
# ══════════════════════════════════════════════
@router.callback_query(ChatCD.filter(F.action == ChatAction.members), CheckUser())
@router.callback_query(MembersCD.filter(F.action == MembersAction.list), CheckUser())
@router.callback_query(MembersCD.filter(F.action == MembersAction.page), CheckUser())
async def cb_members_list(call: types.CallbackQuery, callback_data, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return
    await show_members_list(call, callback_data.chat_id, page=getattr(callback_data, 'page', 0))
    await call.answer()


# ══════════════════════════════════════════════
#  Детали участника
# ══════════════════════════════════════════════
@router.callback_query(MembersCD.filter(F.action == MembersAction.select), CheckUser())
async def cb_member_detail(call: types.CallbackQuery, callback_data: MembersCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return
    await show_member_detail(call, callback_data.chat_id, callback_data.member_id)
    await call.answer()


# ══════════════════════════════════════════════
#  Заморозить участника
# ══════════════════════════════════════════════
@router.callback_query(MembersCD.filter(F.action == MembersAction.freeze), CheckUser())
async def cb_freeze_member_ask(call: types.CallbackQuery, callback_data: MembersCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    member_id = callback_data.member_id
    with models.connector:
        member = models.ChatMember.get_or_none(models.ChatMember.id == member_id)

    action = "разморозить" if (member and member.is_blocked) else "заморозить"
    name = member.display_name if member else str(member_id)

    await call.message.edit_text(
        f"❓ {action.capitalize()} участника <b>{name}</b>?",
        reply_markup=member_freeze_confirm_keyboard(
            callback_data.chat_id, member_id, member.is_blocked if member else False
        ),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(MembersCD.filter(F.action == MembersAction.freeze_confirm), CheckUser())
async def cb_freeze_member_confirm(call: types.CallbackQuery, callback_data: MembersCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    confirmed = callback_data.page == 1
    if not confirmed:
        await call.message.delete()
        await call.answer("Отменено")
        return

    member_id = callback_data.member_id
    chat_id = callback_data.chat_id

    with models.connector:
        member = models.ChatMember.get_or_none(models.ChatMember.id == member_id)
        if not member:
            await call.answer("Участник не найден", show_alert=True)
            return
        member.is_blocked = not member.is_blocked
        member.save()
        is_blocked = member.is_blocked

    action = "заморожен ❄️" if is_blocked else "разморожен 🔥"
    await show_member_detail(call, chat_id, member_id, prefix=f"✅ Участник {action}.")
    await call.answer()


# ══════════════════════════════════════════════
#  Удалить участника из чата
# ══════════════════════════════════════════════
@router.callback_query(MembersCD.filter(F.action == MembersAction.remove), CheckUser())
async def cb_remove_member_ask(call: types.CallbackQuery, callback_data: MembersCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    member_id = callback_data.member_id
    with models.connector:
        member = models.ChatMember.get_or_none(models.ChatMember.id == member_id)
    name = member.display_name if member else str(member_id)

    await call.message.edit_text(
        f"❓ Удалить <b>{name}</b> из чата?",
        reply_markup=member_remove_confirm_keyboard(callback_data.chat_id, member_id),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(MembersCD.filter(F.action == MembersAction.remove_confirm), CheckUser())
async def cb_remove_member_confirm(call: types.CallbackQuery, callback_data: MembersCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    confirmed = callback_data.page == 1
    if not confirmed:
        await call.message.delete()
        await call.answer("Отменено")
        return

    member_id = callback_data.member_id
    chat_id = callback_data.chat_id

    with models.connector:
        member = models.ChatMember.get_or_none(models.ChatMember.id == member_id)
        name = member.display_name if member else str(member_id)
        user_tg_id = member.user_id_id if member else None
        if member:
            member.delete_instance()

    if user_tg_id:
        try:
            with models.connector:
                chat = models.Chat.get_or_none(models.Chat.id == chat_id)
            await call.bot.send_message(
                user_tg_id,
                f"ℹ️ Вы были удалены из чата <b>{chat.title if chat else chat_id}</b>.",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await show_members_list(call, chat_id, prefix=f"✅ {name} удалён из чата.")
    await call.answer()


# ══════════════════════════════════════════════
#  Добавить участника
# ══════════════════════════════════════════════
@router.callback_query(MembersCD.filter(F.action == MembersAction.add), CheckUser())
async def cb_add_member(call: types.CallbackQuery, callback_data: MembersCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    chat_id = callback_data.chat_id

    with models.connector:
        existing_profile_ids = [
            m.profile_id_id for m in
            models.ChatMember.select().where(
                (models.ChatMember.chat_id == chat_id) &
                (models.ChatMember.profile_id.is_null(False))
            )
        ]
        existing_user_ids = [
            m.user_id_id for m in
            models.ChatMember.select().where(
                (models.ChatMember.chat_id == chat_id) &
                (models.ChatMember.user_id.is_null(False))
            )
        ]
        profiles = list(
            models.Profile.select().where(
                models.Profile.id.not_in(existing_profile_ids) if existing_profile_ids
                else models.Profile.id.is_null(False)
            )
        )
        profile_user_ids = [p.user_id_id for p in models.Profile.select() if p.user_id_id]
        all_exclude_user_ids = list(set(profile_user_ids + existing_user_ids))
        tg_users = list(
            models.UserTelegram.select().where(
                models.UserTelegram.id.not_in(all_exclude_user_ids)
            )
        ) if all_exclude_user_ids else list(models.UserTelegram.select())

    await call.message.edit_text(
        "➕ <b>Добавить участника</b>\n\nВыберите профиль или пригласите по ссылке:",
        reply_markup=add_member_keyboard(chat_id, profiles, tg_users),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(MembersCD.filter(F.action == MembersAction.add_profile), CheckUser())
async def cb_add_profile_to_chat(call: types.CallbackQuery, callback_data: MembersCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    chat_id = callback_data.chat_id
    profile_id = callback_data.profile_id

    with models.connector:
        profile = models.Profile.get_or_none(models.Profile.id == profile_id)
        if not profile:
            await call.answer("Профиль не найден", show_alert=True)
            return

        existing = models.ChatMember.get_or_none(
            (models.ChatMember.chat_id == chat_id) &
            (models.ChatMember.profile_id == profile_id)
        )
        if existing:
            await call.answer("Уже в чате", show_alert=True)
            return

        member_type = models.MemberType.ADMIN if profile.is_admin_or_manager else models.MemberType.EMPLOYEE
        models.ChatMember.create(
            chat_id=chat_id,
            user_id=profile.user_id_id,
            profile_id=profile_id,
            member_type=member_type,
        )

    if profile.user_id_id:
        try:
            with models.connector:
                chat = models.Chat.get_or_none(models.Chat.id == chat_id)
            await call.bot.send_message(
                profile.user_id_id,
                f"👋 Вас добавили в чат <b>{chat.title if chat else chat_id}</b>.",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await show_members_list(call, chat_id, prefix=f"✅ {profile.name} добавлен в чат.")
    await call.answer()


# ══════════════════════════════════════════════
#  Многоразовая ссылка-приглашение
# ══════════════════════════════════════════════
@router.callback_query(MembersCD.filter(F.action == MembersAction.invite_link), CheckUser())
async def cb_invite_link(call: types.CallbackQuery, callback_data: MembersCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    chat_id = callback_data.chat_id

    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        if not chat:
            await call.answer("Чат не найден", show_alert=True)
            return

        invite = models.ChatInviteLink.get_or_none(
            (models.ChatInviteLink.chat_id == chat_id) &
            (models.ChatInviteLink.is_active == True)
        )
        if not invite:
            invite = models.ChatInviteLink.create(
                chat_id=chat_id,
                token=secrets.token_urlsafe(16),
            )

    link = f"https://t.me/{config.BOT_USERNAME}?start=con_{invite.token}"

    await call.message.edit_text(
        f"🔗 <b>Многоразовая ссылка для чата «{chat.title}»</b>\n\n"
        f"По этой ссылке может перейти любой пользователь и подключиться к чату.\n"
        f"Ссылка <b>многоразовая</b> — её можно раздавать свободно.\n\n"
        f"<code>{link}</code>\n\n"
        f"ℹ️ Если у пользователя есть профиль сотрудника — он подключится как сотрудник.\n"
        f"Если нет — как клиент.",
        reply_markup=invite_link_keyboard(chat_id),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(MembersCD.filter(F.action == MembersAction.reset_invite), CheckUser())
async def cb_reset_invite_link(call: types.CallbackQuery, callback_data: MembersCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    chat_id = callback_data.chat_id

    with models.connector:
        models.ChatInviteLink.update(is_active=False).where(
            models.ChatInviteLink.chat_id == chat_id
        ).execute()
        invite = models.ChatInviteLink.create(
            chat_id=chat_id,
            token=secrets.token_urlsafe(16),
        )
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)

    link = f"https://t.me/{config.BOT_USERNAME}?start=con_{invite.token}"

    await call.message.edit_text(
        f"✅ Ссылка обновлена.\n\n"
        f"🔗 <b>Новая ссылка для чата «{chat.title if chat else chat_id}»</b>\n\n"
        f"<code>{link}</code>",
        reply_markup=invite_link_keyboard(chat_id),
        parse_mode="HTML",
    )
    await call.answer()


# ══════════════════════════════════════════════
#  Тег/псевдоним участника (только для администратора)
# ══════════════════════════════════════════════

@router.callback_query(MembersCD.filter(F.action == MembersAction.edit_alias), CheckUser())
async def cb_edit_alias_start(
    call: types.CallbackQuery,
    callback_data: MembersCD,
    state: FSMContext,
    is_admin_or_manager: bool,
):
    """Запускает FSM для ввода нового тега участника."""
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    member_id = callback_data.member_id
    chat_id = callback_data.chat_id

    with models.connector:
        member = models.ChatMember.get_or_none(models.ChatMember.id == member_id)
        if not member:
            await call.answer("Участник не найден", show_alert=True)
            return
        current_alias = member.alias or "—"
        real_name = member._real_name

    await state.set_state(MemberAliasState.get_alias)
    await state.update_data(member_id=member_id, chat_id=chat_id)

    from keyboards.kb import cancel_keyboard
    await call.message.edit_text(
        f"🏷 <b>Задать тег участника</b>\n\n"
        f"Участник: <b>{real_name}</b>\n"
        f"Текущий тег: <b>{current_alias}</b>\n\n"
        f"Тег будет отображаться вместо реального имени в рассылках и истории чата.\n"
        f"Реальное имя останется видно только вам (администратору).\n\n"
        f"Введите новый тег (или «-» чтобы очистить):",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()


@router.message(MemberAliasState.get_alias, CheckUser())
async def fsm_member_alias(message: types.Message, state: FSMContext):
    """Сохраняет введённый тег."""
    data = await state.get_data()
    member_id = data["member_id"]
    chat_id = data["chat_id"]
    await state.clear()

    raw = message.text.strip()
    new_alias = None if raw == "-" else raw[:100]  # ограничиваем длину полем модели

    with models.connector:
        member = models.ChatMember.get_or_none(models.ChatMember.id == member_id)
        if not member:
            await message.answer("❌ Участник не найден.")
            return
        member.alias = new_alias
        member.save()

    if new_alias:
        prefix = f"✅ Тег <b>{new_alias}</b> сохранён."
    else:
        prefix = "✅ Тег сброшен. Будет использоваться реальное имя."

    await show_member_detail(message, chat_id, member_id, prefix=prefix)


@router.callback_query(MembersCD.filter(F.action == MembersAction.clear_alias), CheckUser())
async def cb_clear_alias(
    call: types.CallbackQuery,
    callback_data: MembersCD,
    is_admin_or_manager: bool,
):
    """Мгновенно сбрасывает тег без FSM."""
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    member_id = callback_data.member_id
    chat_id = callback_data.chat_id

    with models.connector:
        member = models.ChatMember.get_or_none(models.ChatMember.id == member_id)
        if not member:
            await call.answer("Участник не найден", show_alert=True)
            return
        member.alias = None
        member.save()

    await show_member_detail(call, chat_id, member_id, prefix="✅ Тег сброшен.")
    await call.answer()


# ══════════════════════════════════════════════
#  Разморозить из уведомления о нарушении
# ══════════════════════════════════════════════
@router.callback_query(ViolationCD.filter(F.action == ViolationAction.unfreeze_member), CheckUser())
async def cb_unfreeze_member_from_violation(call: types.CallbackQuery, callback_data: ViolationCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    member_id = callback_data.member_id

    with models.connector:
        member = models.ChatMember.get_or_none(models.ChatMember.id == member_id)
        if not member:
            await call.answer("Участник не найден", show_alert=True)
            return
        member.is_blocked = False
        member.save()
        user_tg_id = member.user_id_id

    if user_tg_id:
        try:
            await call.bot.send_message(user_tg_id, "✅ Ваш доступ к чату восстановлен.")
        except Exception:
            pass

    await call.answer("✅ Участник разморожен", show_alert=True)
    await call.message.edit_reply_markup(reply_markup=None)


@router.callback_query(ViolationCD.filter(F.action == ViolationAction.unfreeze_profile), CheckUser())
async def cb_unfreeze_profile_from_violation(call: types.CallbackQuery, callback_data: ViolationCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    profile_id = callback_data.profile_id

    with models.connector:
        profile = models.Profile.get_or_none(models.Profile.id == profile_id)
        if not profile:
            await call.answer("Профиль не найден", show_alert=True)
            return
        profile.is_blocked = False
        profile.save()

        models.ChatMember.update(is_blocked=False).where(
            models.ChatMember.profile_id == profile_id
        ).execute()

        user_tg_id = profile.user_id_id

    if user_tg_id:
        try:
            await call.bot.send_message(
                user_tg_id,
                "✅ Ваш профиль разморожен. Вы снова можете участвовать в чатах.",
            )
        except Exception:
            pass

    await call.answer("✅ Профиль разморожен", show_alert=True)
    await call.message.edit_reply_markup(reply_markup=None)