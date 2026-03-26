"""
Хендлеры: управление фильтрами (глобальными и по чатам).
Задача: многострочный ввод = несколько фильтров, без описания.
"""
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.text_decorations import html_decoration as hd

import models
from filters import CheckUser
from keyboards import MainMenuCD, MainMenuAction, FiltersCD, FiltersAction, ChatCD, ChatAction
from keyboards.kb import (
    global_filters_keyboard, global_filter_detail_keyboard,
    chat_filters_keyboard, chat_filter_detail_keyboard,
    cancel_keyboard,
)
from states import FilterCreateState

router = Router()


# ══════════════════════════════════════════════
#  Глобальные фильтры
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
        f"🚫 <b>Глобальные фильтры</b> ({len(filters)})\n\nПрименяются ко всем чатам бота.",
        reply_markup=global_filters_keyboard(filters, page=getattr(callback_data, 'page', 0)),
        parse_mode="HTML",
    )
    await call.answer()


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
    await call.message.edit_text(
        f"🌐 <b>Глобальный фильтр</b>\n\n📝 <code>{hd.quote(flt.pattern)}</code>\n📊 {status}",
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
        f"🚫 <b>Глобальные фильтры</b> ({len(filters)})",
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
        "✏️ Введите regex паттерны для глобальных фильтров.\n\n"
        "Каждая строка — отдельный фильтр:",
        reply_markup=cancel_keyboard(),
    )
    await call.answer()


# ══════════════════════════════════════════════
#  Фильтры конкретного чата (из карточки чата)
# ══════════════════════════════════════════════
@router.callback_query(ChatCD.filter(F.action == ChatAction.filters), CheckUser())
async def cb_chat_filters_from_chat(call: types.CallbackQuery, callback_data: ChatCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return
    chat_id = callback_data.chat_id
    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        filters = list(models.ChatFilter.select().where(
            models.ChatFilter.chat_id == chat_id
        ).order_by(models.ChatFilter.date_create))
    await call.message.edit_text(
        f"🚫 <b>Фильтры чата «{chat.title if chat else chat_id}»</b> ({len(filters)})",
        reply_markup=chat_filters_keyboard(filters, chat_id, page=0),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(FiltersCD.filter(F.action == FiltersAction.chat_list), CheckUser())
async def cb_chat_filters_select(call: types.CallbackQuery, callback_data: FiltersCD, is_admin_or_manager: bool):
    if not is_admin_or_manager:
        await call.answer("Недостаточно прав", show_alert=True)
        return
    chat_id = callback_data.chat_id
    with models.connector:
        chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        filters = list(models.ChatFilter.select().where(
            models.ChatFilter.chat_id == chat_id
        ).order_by(models.ChatFilter.date_create))
    await call.message.edit_text(
        f"🚫 <b>Фильтры чата «{chat.title if chat else chat_id}»</b> ({len(filters)})",
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
    await call.message.edit_text(
        f"💬 <b>Фильтр чата</b>\n\n📝 <code>{hd.quote(flt.pattern)}</code>\n📊 {status}",
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
        f"🚫 <b>Фильтры чата «{chat.title if chat else chat_id}»</b> ({len(filters)})",
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
        "✏️ Введите regex паттерны для фильтров чата.\n\n"
        "Каждая строка — отдельный фильтр:",
        reply_markup=cancel_keyboard(),
    )
    await call.answer()


# ══════════════════════════════════════════════
#  FSM: приём паттернов (многострочный, без описания)
# ══════════════════════════════════════════════
@router.message(FilterCreateState.get_pattern, CheckUser())
async def fsm_filter_patterns(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    # Удаляем сообщение пользователя
    try:
        await message.delete()
    except Exception:
        pass

    # Каждая непустая строка — отдельный фильтр
    patterns = [line.strip() for line in message.text.splitlines() if line.strip()]
    if not patterns:
        await message.answer("❌ Не найдено ни одного паттерна.")
        return

    with models.connector:
        if data['filter_type'] == 'global':
            for p in patterns:
                models.GlobalFilter.create(pattern=p)
            filters = list(models.GlobalFilter.select().order_by(models.GlobalFilter.date_create))
        else:
            chat_id = data['chat_id']
            for p in patterns:
                models.ChatFilter.create(chat_id=chat_id, pattern=p)
            filters = list(models.ChatFilter.select().where(
                models.ChatFilter.chat_id == chat_id
            ).order_by(models.ChatFilter.date_create))

    count = len(patterns)

    if data['filter_type'] == 'global':
        await message.answer(
            f"✅ Создано фильтров: {count}\n\n"
            f"🚫 <b>Глобальные фильтры</b> ({len(filters)})",
            reply_markup=global_filters_keyboard(filters),
            parse_mode="HTML",
        )
    else:
        with models.connector:
            chat = models.Chat.get_or_none(models.Chat.id == chat_id)
        await message.answer(
            f"✅ Создано фильтров: {count}\n\n"
            f"🚫 <b>Фильтры чата «{chat.title if chat else chat_id}»</b> ({len(filters)})",
            reply_markup=chat_filters_keyboard(filters, chat_id),
            parse_mode="HTML",
        )