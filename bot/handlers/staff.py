"""
Хендлеры: управление профилями сотрудников.
"""
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from loguru import logger

import models
import config
from filters import CheckUser
from keyboards import MainMenuCD, MainMenuAction, StaffCD, StaffAction
from keyboards.kb import (
    staff_list_keyboard, staff_detail_keyboard,
    staff_delete_confirm_keyboard, profile_type_keyboard,
    cancel_keyboard,
)
from . import *
from states import ProfileCreateState, ProfileEditState

router = Router()


# ══════════════════════════════════════════════
#  Список сотрудников
# ══════════════════════════════════════════════
@router.callback_query(MainMenuCD.filter(F.action == MainMenuAction.staff), CheckUser())
@router.callback_query(StaffCD.filter(F.action == StaffAction.list), CheckUser())
@router.callback_query(StaffCD.filter(F.action == StaffAction.page), CheckUser())
async def cb_staff_list(call: types.CallbackQuery, callback_data, is_admin_or_manager: bool):
    await show_staff_list(call, page=getattr(callback_data, 'page', 0))
    await call.answer()


# ══════════════════════════════════════════════
#  Детали сотрудника
# ══════════════════════════════════════════════
@router.callback_query(StaffCD.filter(F.action == StaffAction.select), CheckUser())
async def cb_staff_detail(call: types.CallbackQuery, callback_data: StaffCD, is_admin_or_manager: bool):
    await show_staff_detail(call, callback_data.profile_id)
    await call.answer()


# ══════════════════════════════════════════════
#  Создание сотрудника
# ══════════════════════════════════════════════
@router.callback_query(StaffCD.filter(F.action == StaffAction.add), CheckUser())
async def cb_add_staff_start(call: types.CallbackQuery, state: FSMContext, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(ProfileCreateState.get_name)
    await call.message.edit_text("✏️ Введите имя нового сотрудника:", reply_markup=cancel_keyboard())
    await call.answer()


@router.message(ProfileCreateState.get_name, CheckUser())
async def fsm_profile_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(ProfileCreateState.get_type)
    await message.answer("👤 Выберите роль:", reply_markup=profile_type_keyboard())


@router.callback_query(F.data.startswith("ptype:"), CheckUser())
async def fsm_profile_type(call: types.CallbackQuery, state: FSMContext):
    current = await state.get_state()
    if current != ProfileCreateState.get_type:
        await call.answer()
        return

    ptype = call.data.split(":")[1]
    await state.update_data(profile_type=ptype)
    await state.set_state(ProfileCreateState.get_position)
    await call.message.edit_text(
        "💼 Введите должность (или «-» чтобы пропустить):",
        reply_markup=cancel_keyboard(),
    )
    await call.answer()


@router.message(ProfileCreateState.get_position, CheckUser())
async def fsm_profile_position(message: types.Message, state: FSMContext, is_admin_or_manager: bool):
    data = await state.get_data()
    position = message.text.strip()
    if position == '-':
        position = None

    await state.clear()

    with models.connector:
        profile = models.Profile.create(
            name=data['name'],
            profile_type=data['profile_type'],
            position=position,
        )

    link = f"https://t.me/{config.BOT_USERNAME}?start=pe_{profile.connect_token}"

    await show_staff_detail(message, profile.id, prefix=f"✅ Сотрудник <b>{profile.name}</b> создан.")


# ══════════════════════════════════════════════
#  Редактирование имени
# ══════════════════════════════════════════════
@router.callback_query(StaffCD.filter(F.action == StaffAction.edit_name), CheckUser())
async def cb_edit_name_start(call: types.CallbackQuery, callback_data: StaffCD, state: FSMContext, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(ProfileEditState.get_name)
    await state.update_data(profile_id=callback_data.profile_id)
    await call.message.edit_text("✏️ Введите новое имя:", reply_markup=cancel_keyboard())
    await call.answer()


@router.message(ProfileEditState.get_name, CheckUser())
async def fsm_edit_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    profile_id = data['profile_id']
    await state.clear()

    with models.connector:
        profile = models.Profile.get_or_none(models.Profile.id == profile_id)
        if profile:
            profile.name = message.text.strip()
            profile.save()

    await show_staff_detail(message, profile_id, prefix="✅ Данные обновлены.")


# ══════════════════════════════════════════════
#  Редактирование должности
# ══════════════════════════════════════════════
@router.callback_query(StaffCD.filter(F.action == StaffAction.edit_position), CheckUser())
async def cb_edit_position_start(call: types.CallbackQuery, callback_data: StaffCD, state: FSMContext, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(ProfileEditState.get_position)
    await state.update_data(profile_id=callback_data.profile_id)
    await call.message.edit_text(
        "💼 Введите новую должность (или «-» чтобы очистить):",
        reply_markup=cancel_keyboard(),
    )
    await call.answer()


@router.message(ProfileEditState.get_position, CheckUser())
async def fsm_edit_position(message: types.Message, state: FSMContext):
    data = await state.get_data()
    profile_id = data['profile_id']
    await state.clear()

    position = message.text.strip()
    if position == '-':
        position = None

    with models.connector:
        profile = models.Profile.get_or_none(models.Profile.id == profile_id)
        if profile:
            profile.position = position
            profile.save()

    await show_staff_detail(message, profile_id, prefix="✅ Данные обновлены.")


# ══════════════════════════════════════════════
#  Удаление сотрудника
# ══════════════════════════════════════════════
@router.callback_query(StaffCD.filter(F.action == StaffAction.delete), CheckUser())
async def cb_delete_staff_ask(call: types.CallbackQuery, callback_data: StaffCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    profile_id = callback_data.profile_id
    with models.connector:
        profile = models.Profile.get_or_none(models.Profile.id == profile_id)
    name = profile.name if profile else str(profile_id)

    await call.message.edit_text(
        f"❓ Удалить сотрудника <b>{name}</b>? Это действие необратимо.",
        reply_markup=staff_delete_confirm_keyboard(profile_id),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(StaffCD.filter(F.action == StaffAction.delete_confirm), CheckUser())
async def cb_delete_staff_confirm(call: types.CallbackQuery, callback_data: StaffCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    confirmed = callback_data.page == 1
    if not confirmed:
        await call.message.delete()
        await call.answer("Отменено")
        return

    profile_id = callback_data.profile_id

    with models.connector:
        profile = models.Profile.get_or_none(models.Profile.id == profile_id)
        if profile:
            profile.delete_instance()

    await call.message.edit_text("✅ Сотрудник удалён.")
    await call.answer()