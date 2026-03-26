"""
Хендлеры: Автоподключение.
"""
from aiogram import Router, F, types
from filters import CheckUser
from keyboards import MainMenuCD, MainMenuAction, AutoConnectCD, AutoConnectAction
from keyboards.kb import autoconnect_keyboard, autoconnect_profile_keyboard, autoconnect_delete_confirm_keyboard
import models

router = Router()


@router.callback_query(MainMenuCD.filter(F.action == MainMenuAction.autoconnect), CheckUser())
@router.callback_query(AutoConnectCD.filter(F.action == AutoConnectAction.back), CheckUser())
async def cb_autoconnect_list(call: types.CallbackQuery, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    with models.connector:
        auto_connects = list(models.AutoConnect.select())

    text = (
        "🔗 <b>Автоподключение</b>\n\n"
        "Профили из этого списка автоматически добавляются в каждый новый чат сразу после его создания.\n\n"
    )
    if auto_connects:
        text += f"Настроено: {len(auto_connects)} профил(ей)"
    else:
        text += "Список пуст."

    await call.message.edit_text(
        text,
        reply_markup=autoconnect_keyboard(auto_connects),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(AutoConnectCD.filter(F.action == AutoConnectAction.add), CheckUser())
async def cb_autoconnect_add(call: types.CallbackQuery, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    with models.connector:
        existing_ids = [ac.profile_id for ac in models.AutoConnect.select()]
        profiles = list(
            models.Profile.select().where(
                models.Profile.id.not_in(existing_ids) if existing_ids
                else models.Profile.id.is_null(False)
            )
        )

    if not profiles:
        await call.answer("Все профили уже добавлены в автоподключение", show_alert=True)
        return

    await call.message.edit_text(
        "👤 Выберите профиль для автоподключения:",
        reply_markup=autoconnect_profile_keyboard(profiles),
    )
    await call.answer()


@router.callback_query(AutoConnectCD.filter(F.action == AutoConnectAction.add_profile), CheckUser())
async def cb_autoconnect_add_profile(call: types.CallbackQuery, callback_data: AutoConnectCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    with models.connector:
        profile = models.Profile.get_or_none(models.Profile.id == callback_data.profile_id)
        if not profile:
            await call.answer("Профиль не найден", show_alert=True)
            return

        existing = models.AutoConnect.get_or_none(
            models.AutoConnect.profile_id == callback_data.profile_id
        )
        if not existing:
            models.AutoConnect.create(profile=callback_data.profile_id)

        auto_connects = list(models.AutoConnect.select())

    await call.message.edit_text(
        f"✅ <b>{profile.name}</b> добавлен в автоподключение.\n\n"
        "🔗 <b>Автоподключение</b>\n\n"
        "Профили из этого списка автоматически добавляются в каждый новый чат.",
        reply_markup=autoconnect_keyboard(auto_connects),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(AutoConnectCD.filter(F.action == AutoConnectAction.delete), CheckUser())
async def cb_autoconnect_delete_ask(call: types.CallbackQuery, callback_data: AutoConnectCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    with models.connector:
        ac = models.AutoConnect.get_or_none(models.AutoConnect.id == callback_data.ac_id)
        name = ac.profile.name if ac else str(callback_data.ac_id)

    await call.message.edit_text(
        f"❓ Удалить <b>{name}</b> из автоподключения?",
        reply_markup=autoconnect_delete_confirm_keyboard(callback_data.ac_id),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(AutoConnectCD.filter(F.action == AutoConnectAction.delete_confirm), CheckUser())
async def cb_autoconnect_delete_confirm(call: types.CallbackQuery, callback_data: AutoConnectCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    with models.connector:
        ac = models.AutoConnect.get_or_none(models.AutoConnect.id == callback_data.ac_id)
        if ac:
            ac.delete_instance()
        auto_connects = list(models.AutoConnect.select())

    await call.message.edit_text(
        "✅ Удалено из автоподключения.\n\n"
        "🔗 <b>Автоподключение</b>",
        reply_markup=autoconnect_keyboard(auto_connects),
        parse_mode="HTML",
    )
    await call.answer()
