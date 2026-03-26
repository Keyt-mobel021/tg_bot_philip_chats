"""
Хендлеры: управление фильтрами (глобальными и по чатам).
"""
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

import models
from filters import CheckUser
from keyboards import MainMenuCD, MainMenuAction, FiltersCD, FiltersAction
from keyboards.kb import (
    global_filters_keyboard, global_filter_detail_keyboard,
    chat_filters_keyboard, chat_filter_detail_keyboard,
    chats_for_filter_keyboard, cancel_keyboard,
)
from states import FilterCreateState

router = Router()


# ══════════════════════════════════════════════
#  Меню фильтров — сразу глобальный список
# ══════════════════════════════════════════════
@router.callback_query(MainMenuCD.filter(F.action == MainMenuAction.filters), CheckUser())
@router.callback_query(FiltersCD.filter(F.action == FiltersAction.list), CheckUser())
@router.callback_query(FiltersCD.filter(F.action == FiltersAction.back), CheckUser())
@router.callback_query(FiltersCD.filter(F.action == FiltersAction.global_list), CheckUser())
async def cb_filters_menu(call: types.CallbackQuery, callback_data, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    with models.connector:
        filters = list(models.GlobalFilter.select().order_by(models.GlobalFilter.date_create))

    await call.message.edit_text(
        f"🚫 <b>Глобальные фильтры</b> ({len(filters)})\n\n"
        "Применяются ко всем чатам бота.",
        reply_markup=global_filters_keyboard(filters, page=getattr(callback_data, 'page', 0)),
        parse_mode="HTML",
    )
    await call.answer()


# ══════════════════════════════════════════════
#  Детали глобального фильтра
# ══════════════════════════════════════════════
@router.callback_query(FiltersCD.filter(F.action == FiltersAction.select_global), CheckUser())
async def cb_global_filter_detail(call: types.CallbackQuery, callback_data: FiltersCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    with models.connector:
        flt = models.GlobalFilter.get_or_none(models.GlobalFilter.id == callback_data.filter_id)

    if not flt:
        await call.answer("Фильтр не найден", show_alert=True)
        return

    status = "✅ Активен" if flt.is_active else "⏸ Неактивен"
    text = (
        f"🌐 <b>Глобальный фильтр</b>\n\n"
        f"📝 Паттерн: <code>{flt.pattern}</code>\n"
        f"📊 Статус: {status}\n"
    )
    if flt.description:
        text += f"💬 Описание: {flt.description}"

    await call.message.edit_text(
        text,
        reply_markup=global_filter_detail_keyboard(flt.id, flt.is_active),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(FiltersCD.filter(F.action == FiltersAction.toggle_global), CheckUser())
async def cb_toggle_global_filter(call: types.CallbackQuery, callback_data: FiltersCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    with models.connector:
        flt = models.GlobalFilter.get_or_none(models.GlobalFilter.id == callback_data.filter_id)
        if flt:
            flt.is_active = not flt.is_active
            flt.save()

    await call.answer("✅ Статус обновлён")
    await cb_global_filter_detail(call, callback_data, is_admin_or_manager)


@router.callback_query(FiltersCD.filter(F.action == FiltersAction.delete_global), CheckUser())
async def cb_delete_global_filter(call: types.CallbackQuery, callback_data: FiltersCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    with models.connector:
        flt = models.GlobalFilter.get_or_none(models.GlobalFilter.id == callback_data.filter_id)
        if flt:
            flt.delete_instance()
        filters = list(models.GlobalFilter.select())

    await call.answer("✅ Фильтр удалён")
    await call.message.edit_text(
        f"🌐 <b>Глобальные фильтры</b> ({len(filters)})",
        reply_markup=global_filters_keyboard(filters),
        parse_mode="HTML",
    )


@router.callback_query(FiltersCD.filter(F.action == FiltersAction.create_global), CheckUser())
async def cb_create_global_filter_start(call: types.CallbackQuery, state: FSMContext, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(FilterCreateState.get_pattern)
    await state.update_data(filter_type="global", chat_id=0)
    await call.message.edit_text(
        "✏️ Введите regex паттерн для глобального фильтра:",
        reply_markup=cancel_keyboard(),
    )
    await call.answer()


# ══════════════════════════════════════════════
#  Фильтры по чатам
# ══════════════════════════════════════════════
@router.callback_query(FiltersCD.filter(F.action == FiltersAction.chat_list), CheckUser())
async def cb_chat_filters_select(call: types.CallbackQuery, callback_data: FiltersCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    chat_id = callback_data.chat_id

    if not chat_id:
        with models.connector:
            chats = list(models.Chat.select().where(models.Chat.is_visible == True))
        await call.message.edit_text(
            "💬 Выберите чат для просмотра фильтров:",
            reply_markup=chats_for_filter_keyboard(chats),
        )
        await call.answer()
        return

    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        filters = list(models.ChatFilter.select().where(
            models.ChatFilter.chat_id == chat_id
        ).order_by(models.ChatFilter.date_create))

    await call.message.edit_text(
        f"💬 <b>Фильтры чата «{chat.title if chat else chat_id}»</b> ({len(filters)})",
        reply_markup=chat_filters_keyboard(filters, chat_id, callback_data.page),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(FiltersCD.filter(F.action == FiltersAction.select), CheckUser())
async def cb_chat_filter_detail(call: types.CallbackQuery, callback_data: FiltersCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    with models.connector:
        flt = models.ChatFilter.get_or_none(models.ChatFilter.id == callback_data.filter_id)

    if not flt:
        await call.answer("Фильтр не найден", show_alert=True)
        return

    status = "✅ Активен" if flt.is_active else "⏸ Неактивен"
    text = (
        f"💬 <b>Фильтр чата</b>\n\n"
        f"📝 Паттерн: <code>{flt.pattern}</code>\n"
        f"📊 Статус: {status}\n"
    )
    if flt.description:
        text += f"💬 Описание: {flt.description}"

    await call.message.edit_text(
        text,
        reply_markup=chat_filter_detail_keyboard(flt.id, callback_data.chat_id, flt.is_active),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(FiltersCD.filter(F.action == FiltersAction.toggle), CheckUser())
async def cb_toggle_chat_filter(call: types.CallbackQuery, callback_data: FiltersCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    with models.connector:
        flt = models.ChatFilter.get_or_none(models.ChatFilter.id == callback_data.filter_id)
        if flt:
            flt.is_active = not flt.is_active
            flt.save()

    await call.answer("✅ Статус обновлён")
    await cb_chat_filter_detail(call, callback_data, is_admin_or_manager)


@router.callback_query(FiltersCD.filter(F.action == FiltersAction.delete), CheckUser())
async def cb_delete_chat_filter(call: types.CallbackQuery, callback_data: FiltersCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    chat_id = callback_data.chat_id

    with models.connector:
        flt = models.ChatFilter.get_or_none(models.ChatFilter.id == callback_data.filter_id)
        if flt:
            flt.delete_instance()
        filters = list(models.ChatFilter.select().where(models.ChatFilter.chat_id == chat_id))
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)

    await call.answer("✅ Фильтр удалён")
    await call.message.edit_text(
        f"💬 <b>Фильтры чата «{chat.title if chat else chat_id}»</b> ({len(filters)})",
        reply_markup=chat_filters_keyboard(filters, chat_id),
        parse_mode="HTML",
    )


@router.callback_query(FiltersCD.filter(F.action == FiltersAction.create), CheckUser())
async def cb_create_chat_filter_start(call: types.CallbackQuery, callback_data: FiltersCD, state: FSMContext, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    await state.set_state(FilterCreateState.get_pattern)
    await state.update_data(filter_type="chat", chat_id=callback_data.chat_id)
    await call.message.edit_text(
        "✏️ Введите regex паттерн для фильтра:",
        reply_markup=cancel_keyboard(),
    )
    await call.answer()


# ══════════════════════════════════════════════
#  FSM создания фильтра
# ══════════════════════════════════════════════
@router.message(FilterCreateState.get_pattern, CheckUser())
async def fsm_filter_pattern(message: types.Message, state: FSMContext):
    await state.update_data(pattern=message.text.strip())
    await state.set_state(FilterCreateState.get_description)
    await message.answer(
        "📝 Введите описание фильтра (или «-» чтобы пропустить):",
        reply_markup=cancel_keyboard(),
    )


@router.message(FilterCreateState.get_description, CheckUser())
async def fsm_filter_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    description = message.text.strip()
    if description == '-':
        description = None

    await state.clear()

    with models.connector:
        if data['filter_type'] == 'global':
            models.GlobalFilter.create(
                pattern=data['pattern'],
                description=description,
            )
            await message.answer("✅ Глобальный фильтр создан.")
        else:
            models.ChatFilter.create(
                chat_id=data['chat_id'],
                pattern=data['pattern'],
                description=description,
            )
            await message.answer("✅ Фильтр чата создан.")