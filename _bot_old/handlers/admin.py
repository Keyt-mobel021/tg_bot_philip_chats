import re
from aiogram import types, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from html import escape

from filters import CheckAdmin
from states import FilterCreateState, FilterEditState, ThresholdState
from keyboards.kb import (
    main_menu_keyboard, chats_keyboard, chat_settings_keyboard,
    filters_keyboard, cancel_keyboard, back_to_chat_keyboard, blocked_users_keyboard, blocked_user_detail_keyboard
)
from keyboards import (
    MenuCallbackData, MenuAction,
    ChatsCallbackData, ChatsAction,
    ChatSettingsCallbackData, ChatSettingsAction,
    FiltersCallbackData, FiltersAction, BlockedCallbackData, BlockedAction
)
import models
from loguru import logger

router = Router()

REGEX101_LINK = "🔗 Тестировать regex: https://regex101.com/"


# ─── Helpers ────────────────────────────────────────────────────────────────

def get_chat_info_text(chat: models.ChatGroup) -> str:
    with models.connector:
        filters_count = models.ChatFilter.select().where(models.ChatFilter.chat_id == chat.id).count()
        active_filters = models.ChatFilter.select().where(
            (models.ChatFilter.chat_id == chat.id) & (models.ChatFilter.is_active == True)
        ).count()

    status = "✅ Активен" if chat.is_active else "⏸ Приостановлен"
    icon = "👥" if chat.is_group else "👤"

    return (
        f"{icon} <b>{chat.title or chat.id}</b>\n\n"
        f"🆔 ID: <code>{chat.id}</code>\n"
        f"📊 Статус: {status}\n"
        f"🎚 Порог нечеткого совпадения: <b>{chat.fuzzy_threshold}%</b>\n"
        f"🔍 Фильтров: <b>{filters_count}</b> (активных: {active_filters})\n"
    )


# ─── /start ─────────────────────────────────────────────────────────────────

@router.message(Command("start"), CheckAdmin())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Добро пожаловать в панель управления фильтрами!\n\n"
        "Здесь вы можете управлять чатами и настраивать фильтры сообщений.",
        reply_markup=main_menu_keyboard()
    )


# ─── Главное меню → Чаты ────────────────────────────────────────────────────

@router.callback_query(MenuCallbackData.filter(F.action == MenuAction.chats), CheckAdmin())
async def cb_menu_chats(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    with models.connector:
        chats = list(models.ChatGroup.select().order_by(models.ChatGroup.title))

    if not chats:
        await callback.message.edit_text(
            "💬 <b>Список чатов пуст</b>\n\nДобавьте бота в группу и напишите /start в той группе.",
            reply_markup=main_menu_keyboard()
        )
        return await callback.answer()

    await callback.message.edit_text(
        f"💬 <b>Чаты</b> ({len(chats)} шт.)\n\nВыберите чат для настройки:",
        reply_markup=chats_keyboard(chats, page=0)
    )
    await callback.answer()


# ─── Пагинация чатов ────────────────────────────────────────────────────────

@router.callback_query(ChatsCallbackData.filter(F.action == ChatsAction.page), CheckAdmin())
async def cb_chats_page(callback: types.CallbackQuery, callback_data: ChatsCallbackData):
    with models.connector:
        chats = list(models.ChatGroup.select().order_by(models.ChatGroup.title))

    await callback.message.edit_text(
        f"💬 <b>Чаты</b> ({len(chats)} шт.)\n\nВыберите чат для настройки:",
        reply_markup=chats_keyboard(chats, page=callback_data.page)
    )
    await callback.answer()


# ─── Назад в главное меню ───────────────────────────────────────────────────

@router.callback_query(ChatsCallbackData.filter(F.action == ChatsAction.back), CheckAdmin())
async def cb_chats_back(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "👋 Панель управления фильтрами\n\nВыберите раздел:",
        reply_markup=main_menu_keyboard()
    )
    await callback.answer()


# ─── Выбор чата → настройки ─────────────────────────────────────────────────

@router.callback_query(ChatsCallbackData.filter(F.action == ChatsAction.select), CheckAdmin())
async def cb_chat_select(callback: types.CallbackQuery, callback_data: ChatsCallbackData, state: FSMContext):
    await state.update_data(current_chat_id=callback_data.chat_id, chat_list_page=callback_data.page)

    with models.connector:
        chat = models.ChatGroup.get_or_none(models.ChatGroup.id == callback_data.chat_id)

    if not chat:
        await callback.answer("❌ Чат не найден", show_alert=True)
        return

    await callback.message.edit_text(
        get_chat_info_text(chat),
        reply_markup=chat_settings_keyboard(chat.id, chat.is_active)
    )
    await callback.answer()


# ─── Назад к списку чатов из настроек ───────────────────────────────────────

@router.callback_query(ChatSettingsCallbackData.filter(F.action == ChatSettingsAction.back), CheckAdmin())
async def cb_chat_settings_back(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get("chat_list_page", 0)

    with models.connector:
        chats = list(models.ChatGroup.select().order_by(models.ChatGroup.title))

    await callback.message.edit_text(
        f"💬 <b>Чаты</b> ({len(chats)} шт.)\n\nВыберите чат для настройки:",
        reply_markup=chats_keyboard(chats, page=page)
    )
    await callback.answer()


# ─── Переключить активность чата ────────────────────────────────────────────

@router.callback_query(ChatSettingsCallbackData.filter(F.action == ChatSettingsAction.toggle_active), CheckAdmin())
async def cb_toggle_active(callback: types.CallbackQuery, callback_data: ChatSettingsCallbackData):
    with models.connector:
        chat = models.ChatGroup.get_or_none(models.ChatGroup.id == callback_data.chat_id)
        if not chat:
            return await callback.answer("❌ Чат не найден", show_alert=True)
        chat.is_active = not chat.is_active
        chat.save()

    status = "✅ активирован" if chat.is_active else "⏸ приостановлен"
    await callback.answer(f"Мониторинг {status}", show_alert=True)
    await callback.message.edit_text(
        get_chat_info_text(chat),
        reply_markup=chat_settings_keyboard(chat.id, chat.is_active)
    )


# ─── Установить порог нечеткого совпадения ──────────────────────────────────

@router.callback_query(ChatSettingsCallbackData.filter(F.action == ChatSettingsAction.set_threshold), CheckAdmin())
async def cb_set_threshold(callback: types.CallbackQuery, callback_data: ChatSettingsCallbackData, state: FSMContext):
    await state.set_state(ThresholdState.get_threshold)
    await state.update_data(current_chat_id=callback_data.chat_id)

    with models.connector:
        chat = models.ChatGroup.get_or_none(models.ChatGroup.id == callback_data.chat_id)

    await callback.message.edit_text(
        f"⚙️ <b>Порог нечеткого совпадения</b>\n\n"
        f"Текущий порог: <b>{chat.fuzzy_threshold}%</b>\n\n"
        f"Введите новый порог от 0 до 100.\n"
        f"<blockquote>Чем выше значение, тем строже проверка.\n"
        f"Рекомендуется: 75-85</blockquote>",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(ThresholdState.get_threshold, CheckAdmin())
async def process_threshold(message: types.Message, state: FSMContext):
    try:
        threshold = int(message.text.strip())
        if not (0 <= threshold <= 100):
            raise ValueError
    except ValueError:
        return await message.answer(
            "❌ Введите число от 0 до 100",
            reply_markup=cancel_keyboard()
        )

    data = await state.get_data()
    chat_id = data.get("current_chat_id")

    with models.connector:
        chat = models.ChatGroup.get_or_none(models.ChatGroup.id == chat_id)
        if not chat:
            await state.clear()
            return await message.answer("❌ Чат не найден")
        chat.fuzzy_threshold = threshold
        chat.save()

    await state.clear()
    await message.answer(
        f"✅ Порог установлен: <b>{threshold}%</b>",
        reply_markup=back_to_chat_keyboard(chat_id)
    )


# ─── Создать фильтр ─────────────────────────────────────────────────────────

@router.callback_query(ChatSettingsCallbackData.filter(F.action == ChatSettingsAction.create_filter), CheckAdmin())
async def cb_create_filter(callback: types.CallbackQuery, callback_data: ChatSettingsCallbackData, state: FSMContext):
    await state.set_state(FilterCreateState.get_pattern)
    await state.update_data(current_chat_id=callback_data.chat_id)

    await callback.message.edit_text(
        "➕ <b>Создание фильтров</b>\n\n"
        "Введите одно или несколько регулярных выражений — <b>каждое с новой строки</b>.\n\n"
        "<blockquote>Примеры:\n"
        r"• <code>\+7\d{10}</code> — номера телефонов" + "\n"
        r"• <code>@\w+</code> — упоминания Telegram" + "\n"
        r"• <code>https?://\S+</code> — ссылки" + "\n"
        r"• <code>(?i)(телефон|созвонимся|звоните)</code> — слова</blockquote>" + "\n\n"
        f"{REGEX101_LINK}",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(FilterCreateState.get_pattern, CheckAdmin())
async def process_create_filter(message: types.Message, state: FSMContext):
    lines = [line.strip() for line in message.text.strip().splitlines() if line.strip()]

    data = await state.get_data()
    chat_id = data.get("current_chat_id")

    with models.connector:
        chat = models.ChatGroup.get_or_none(models.ChatGroup.id == chat_id)
        if not chat:
            await state.clear()
            return await message.answer("❌ Чат не найден")

    created = []
    errors = []

    for line in lines:
        try:
            re.compile(line)
            with models.connector:
                models.ChatFilter.create(chat_id=chat, pattern=line)
            created.append(line)
        except re.error as e:
            errors.append(f"<code>{escape(line)}</code> — {e}")

    await state.clear()

    text = ""
    if created:
        text += f"✅ Создано фильтров: <b>{len(created)}</b>\n"
        text += "\n".join(f"• <code>{escape(p)}</code>" for p in created)
    if errors:
        text += f"\n\n❌ Ошибки ({len(errors)}):\n"
        text += "\n".join(f"{escape(e)}" for e in errors)

    await message.answer(text, reply_markup=back_to_chat_keyboard(chat_id))


# ─── Редактировать фильтр ───────────────────────────────────────────────────

@router.callback_query(ChatSettingsCallbackData.filter(F.action == ChatSettingsAction.edit_filter), CheckAdmin())
async def cb_edit_filter_list(callback: types.CallbackQuery, callback_data: ChatSettingsCallbackData, state: FSMContext):
    with models.connector:
        filters = list(models.ChatFilter.select().where(
            models.ChatFilter.chat_id == callback_data.chat_id
        ).order_by(models.ChatFilter.date_create))

    if not filters:
        await callback.answer("ℹ️ Фильтров нет. Сначала создайте фильтр.", show_alert=True)
        return

    await state.update_data(current_chat_id=callback_data.chat_id)
    await callback.message.edit_text(
        f"✏️ <b>Редактирование фильтра</b>\n\nВыберите фильтр:",
        reply_markup=filters_keyboard(callback_data.chat_id, filters, mode="edit")
    )
    await callback.answer()


@router.callback_query(FiltersCallbackData.filter((F.action == FiltersAction.select) & (F.mode == "edit")), CheckAdmin())
async def cb_edit_filter_select(callback: types.CallbackQuery, callback_data: FiltersCallbackData, state: FSMContext):
    with models.connector:
        f = models.ChatFilter.get_or_none(models.ChatFilter.id == callback_data.filter_id)

    if not f:
        await callback.answer("❌ Фильтр не найден", show_alert=True)
        return

    await state.set_state(FilterEditState.get_pattern)
    await state.update_data(
        current_chat_id=callback_data.chat_id,
        current_filter_id=callback_data.filter_id
    )

    await callback.message.edit_text(
        f"✏️ <b>Редактирование фильтра</b>\n\n"
        f"Текущее выражение:\n<code>{escape(f.pattern)}</code>\n\n"
        f"Введите новое регулярное выражение:\n\n"
        f"{REGEX101_LINK}",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(FilterEditState.get_pattern, CheckAdmin())
async def process_edit_filter(message: types.Message, state: FSMContext):
    pattern = message.text.strip()

    try:
        re.compile(pattern)
    except re.error as e:
        return await message.answer(
            f"❌ Некорректное выражение:\n<code>{e}</code>\n\n"
            f"Попробуйте снова:\n{REGEX101_LINK}",
            reply_markup=cancel_keyboard()
        )

    data = await state.get_data()
    filter_id = data.get("current_filter_id")
    chat_id = data.get("current_chat_id")

    with models.connector:
        f = models.ChatFilter.get_or_none(models.ChatFilter.id == filter_id)
        if not f:
            await state.clear()
            return await message.answer("❌ Фильтр не найден")
        f.pattern = pattern
        f.save()

    await state.clear()
    await message.answer(
        f"✅ Фильтр обновлён!\n\n<code>{escape(pattern)}</code>",
        reply_markup=back_to_chat_keyboard(chat_id)
    )


# ─── Удалить фильтр ─────────────────────────────────────────────────────────

@router.callback_query(ChatSettingsCallbackData.filter(F.action == ChatSettingsAction.delete_filter), CheckAdmin())
async def cb_delete_filter_list(callback: types.CallbackQuery, callback_data: ChatSettingsCallbackData, state: FSMContext):
    with models.connector:
        filters = list(models.ChatFilter.select().where(
            models.ChatFilter.chat_id == callback_data.chat_id
        ).order_by(models.ChatFilter.date_create))

    if not filters:
        await callback.answer("ℹ️ Фильтров нет.", show_alert=True)
        return

    await state.update_data(current_chat_id=callback_data.chat_id)
    await callback.message.edit_text(
        f"🗑 <b>Удаление фильтра</b>\n\nВыберите фильтр для удаления:",
        reply_markup=filters_keyboard(callback_data.chat_id, filters, mode="delete")
    )
    await callback.answer()


@router.callback_query(FiltersCallbackData.filter((F.action == FiltersAction.select) & (F.mode == "delete")), CheckAdmin())
async def cb_delete_filter_confirm(callback: types.CallbackQuery, callback_data: FiltersCallbackData, state: FSMContext):
    with models.connector:
        f = models.ChatFilter.get_or_none(models.ChatFilter.id == callback_data.filter_id)
        if not f:
            await callback.answer("❌ Фильтр не найден", show_alert=True)
            return
        pattern = f.pattern
        chat_id = callback_data.chat_id
        f.delete_instance()

    await callback.answer("🗑 Фильтр удалён", show_alert=True)

    # Возврат к настройкам чата
    with models.connector:
        chat = models.ChatGroup.get_or_none(models.ChatGroup.id == chat_id)

    await callback.message.edit_text(
        f"✅ Фильтр удалён:\n<code>{escape(pattern)}</code>\n\n" + get_chat_info_text(chat),
        reply_markup=chat_settings_keyboard(chat_id, chat.is_active)
    )


# ─── Пагинация фильтров ──────────────────────────────────────────────────────

@router.callback_query(FiltersCallbackData.filter(F.action == FiltersAction.page), CheckAdmin())
async def cb_filters_page(callback: types.CallbackQuery, callback_data: FiltersCallbackData):
    with models.connector:
        filters = list(models.ChatFilter.select().where(
            models.ChatFilter.chat_id == callback_data.chat_id
        ).order_by(models.ChatFilter.date_create))

    mode = callback_data.mode
    title = "✏️ Редактирование фильтра" if mode == "edit" else "🗑 Удаление фильтра"
    await callback.message.edit_text(
        f"{title}\n\nВыберите фильтр:",
        reply_markup=filters_keyboard(callback_data.chat_id, filters, page=callback_data.page, mode=mode)
    )
    await callback.answer()


# ─── Назад из списка фильтров ───────────────────────────────────────────────

@router.callback_query(FiltersCallbackData.filter(F.action == FiltersAction.back), CheckAdmin())
async def cb_filters_back(callback: types.CallbackQuery, callback_data: FiltersCallbackData):
    with models.connector:
        chat = models.ChatGroup.get_or_none(models.ChatGroup.id == callback_data.chat_id)

    if not chat:
        await callback.answer("❌ Чат не найден", show_alert=True)
        return

    await callback.message.edit_text(
        get_chat_info_text(chat),
        reply_markup=chat_settings_keyboard(chat.id, chat.is_active)
    )
    await callback.answer()


# ─── Универсальная отмена ────────────────────────────────────────────────────

@router.callback_query(F.data == "cancel", CheckAdmin())
async def cb_cancel(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    chat_id = data.get("current_chat_id")
    await state.clear()

    if chat_id:
        with models.connector:
            chat = models.ChatGroup.get_or_none(models.ChatGroup.id == chat_id)
        if chat:
            await callback.message.edit_text(
                get_chat_info_text(chat),
                reply_markup=chat_settings_keyboard(chat.id, chat.is_active)
            )
            return await callback.answer()

    await callback.message.edit_text(
        "Действие отменено. Выберите раздел:",
        reply_markup=main_menu_keyboard()
    )
    await callback.answer()



# ─── Заблокированные пользователи ───────────────────────────────────────────

@router.callback_query(MenuCallbackData.filter(F.action == MenuAction.blocked), CheckAdmin())
async def cb_menu_blocked(callback: types.CallbackQuery):
    with models.connector:
        users = list(models.BlockedUser.select().order_by(models.BlockedUser.date_create.desc()))

    if not users:
        await callback.message.edit_text(
            "🚫 <b>Заблокированные пользователи</b>\n\nСписок пуст.",
            reply_markup=main_menu_keyboard()
        )
        return await callback.answer()

    await callback.message.edit_text(
        f"🚫 <b>Заблокированные пользователи</b> ({len(users)} чел.)",
        reply_markup=blocked_users_keyboard(users)
    )
    await callback.answer()


@router.callback_query(BlockedCallbackData.filter(F.action == BlockedAction.page), CheckAdmin())
async def cb_blocked_page(callback: types.CallbackQuery, callback_data: BlockedCallbackData):
    with models.connector:
        users = list(models.BlockedUser.select().order_by(models.BlockedUser.date_create.desc()))

    await callback.message.edit_text(
        f"🚫 <b>Заблокированные пользователи</b> ({len(users)} чел.)",
        reply_markup=blocked_users_keyboard(users, page=callback_data.page)
    )
    await callback.answer()


@router.callback_query(BlockedCallbackData.filter(F.action == BlockedAction.view), CheckAdmin())
async def cb_blocked_view(callback: types.CallbackQuery, callback_data: BlockedCallbackData):
    with models.connector:
        blocked = models.BlockedUser.get_or_none(models.BlockedUser.id == callback_data.blocked_id)

    if not blocked:
        await callback.answer("❌ Запись не найдена", show_alert=True)
        return

    username_str = f"@{blocked.username}" if blocked.username else "—"
    text = (
        f"🚫 <b>Заблокированный пользователь</b>\n\n"
        f"👤 Имя: <a href='tg://user?id={blocked.user_id}'>{blocked.full_name or '—'}</a>\n"
        f"🔗 Username: {username_str}\n"
        f"🆔 ID: <code>{blocked.user_id}</code>\n"
        f"💬 Чат: <b>{blocked.chat_id.title}</b>\n"
        f"📅 Дата: {blocked.date_create.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"📝 Триггерное сообщение:\n<blockquote>{blocked.trigger_message or '—'}</blockquote>"
    )
    await callback.message.edit_text(text, reply_markup=blocked_user_detail_keyboard(callback_data.blocked_id))
    await callback.answer()


@router.callback_query(BlockedCallbackData.filter(F.action == BlockedAction.unban), CheckAdmin())
async def cb_blocked_unban(callback: types.CallbackQuery, callback_data: BlockedCallbackData):
    with models.connector:
        blocked = models.BlockedUser.get_or_none(models.BlockedUser.id == callback_data.blocked_id)

    if not blocked:
        await callback.answer("❌ Запись не найдена", show_alert=True)
        return

    user_id = blocked.user_id
    chat_id = blocked.chat_id.id
    full_name = blocked.full_name or str(user_id)

    # Разбаниваем
    try:
        await callback.bot.unban_chat_member(chat_id=chat_id, user_id=user_id, only_if_banned=True)
        unban_ok = True
        unban_error = None
    except Exception as e:
        unban_ok = False
        unban_error = str(e)
        logger.warning(f"Failed to unban user {user_id} in chat {chat_id}: {e}")

    if unban_ok:
        with models.connector:
            blocked.delete_instance()
        await callback.answer("✅ Разблокирован", show_alert=True)
        # Возврат к списку
        with models.connector:
            users = list(models.BlockedUser.select().order_by(models.BlockedUser.date_create.desc()))
        if users:
            await callback.message.edit_text(
                f"🚫 <b>Заблокированные пользователи</b> ({len(users)} чел.)",
                reply_markup=blocked_users_keyboard(users)
            )
        else:
            await callback.message.edit_text(
                "🚫 <b>Заблокированные пользователи</b>\n\nСписок пуст.",
                reply_markup=main_menu_keyboard()
            )
    else:
        await callback.answer(f"⚠️ Не удалось разблокировать", show_alert=True)
        await callback.message.edit_text(
            f"❌ <b>Ошибка разблокировки</b>\n\n"
            f"Пользователь: <b>{full_name}</b>\n\n"
            f"Причина: <code>{unban_error}</code>\n\n"
            f"<i>Возможно бот не является администратором или у него недостаточно прав.</i>",
            reply_markup=blocked_user_detail_keyboard(callback_data.blocked_id)
        )


@router.callback_query(BlockedCallbackData.filter(F.action == BlockedAction.back), CheckAdmin())
async def cb_blocked_back(callback: types.CallbackQuery):
    with models.connector:
        users = list(models.BlockedUser.select().order_by(models.BlockedUser.date_create.desc()))

    if users:
        await callback.message.edit_text(
            f"🚫 <b>Заблокированные пользователи</b> ({len(users)} чел.)",
            reply_markup=blocked_users_keyboard(users)
        )
    else:
        await callback.message.edit_text(
            "👋 Панель управления фильтрами\n\nВыберите раздел:",
            reply_markup=main_menu_keyboard()
        )
    await callback.answer()



@router.callback_query(ChatSettingsCallbackData.filter(F.action == ChatSettingsAction.delete_chat), CheckAdmin())
async def cb_delete_chat(callback: types.CallbackQuery, callback_data: ChatSettingsCallbackData, state: FSMContext):
    with models.connector:
        chat = models.ChatGroup.get_or_none(models.ChatGroup.id == callback_data.chat_id)
        if not chat:
            return await callback.answer("❌ Чат не найден", show_alert=True)
        title = chat.title or str(chat.id)
        # Каскадно удалит все фильтры и заблокированных пользователей
        chat.delete_instance(recursive=True)

    await callback.answer(f"🗑 Чат «{title}» удалён", show_alert=True)

    with models.connector:
        chats = list(models.ChatGroup.select().order_by(models.ChatGroup.title))

    if chats:
        await callback.message.edit_text(
            f"💬 <b>Чаты</b> ({len(chats)} шт.)\n\nВыберите чат для настройки:",
            reply_markup=chats_keyboard(chats, page=0)
        )
    else:
        await callback.message.edit_text(
            "👋 Панель управления фильтрами\n\nВыберите раздел:",
            reply_markup=main_menu_keyboard()
        )