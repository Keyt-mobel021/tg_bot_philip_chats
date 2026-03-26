from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards import *
import models
import config
import math


def main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="💬 Чаты", callback_data=MenuCallbackData(action=MenuAction.chats))
    builder.button(text="🚫 Заблокированные", callback_data=MenuCallbackData(action=MenuAction.blocked))
    builder.adjust(1)
    return builder.as_markup()


def chats_keyboard(chats: list, page: int = 0):
    builder = InlineKeyboardBuilder()
    total = len(chats)
    total_pages = max(1, math.ceil(total / config.PAGE_SIZE))
    start = page * config.PAGE_SIZE
    end = start + config.PAGE_SIZE
    page_chats = chats[start:end]

    for chat in page_chats:
        icon = "👥" if chat.is_group else "👤"
        status = "✅" if chat.is_active else "⏸"
        builder.button(
            text=f"{icon} {status} {chat.title or chat.id}",
            callback_data=ChatsCallbackData(action=ChatsAction.select, chat_id=chat.id, page=page)
        )

    # Пагинация
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(("◀️", ChatsCallbackData(action=ChatsAction.page, chat_id=0, page=page - 1)))
        nav_buttons.append((f"{page + 1}/{total_pages}", ChatsCallbackData(action=ChatsAction.page, chat_id=0, page=page)))
        if page < total_pages - 1:
            nav_buttons.append(("▶️", ChatsCallbackData(action=ChatsAction.page, chat_id=0, page=page + 1)))
        for text, cd in nav_buttons:
            builder.button(text=text, callback_data=cd)
        builder.adjust(*([1] * len(page_chats)), len(nav_buttons))
    else:
        builder.adjust(1)

    builder.button(
        text="⬅️ Назад",
        callback_data=ChatsCallbackData(action=ChatsAction.back, chat_id=0, page=0)
    )
    builder.adjust(1)
    return builder.as_markup()


def chat_settings_keyboard(chat_id: int, is_active: bool):
    builder = InlineKeyboardBuilder()
    toggle_text = "⏸ Приостановить" if is_active else "▶️ Активировать"
    builder.button(text="➕ Создать фильтр", callback_data=ChatSettingsCallbackData(action=ChatSettingsAction.create_filter, chat_id=chat_id))
    builder.button(text="✏️ Редактировать фильтр", callback_data=ChatSettingsCallbackData(action=ChatSettingsAction.edit_filter, chat_id=chat_id))
    builder.button(text="🗑 Удалить фильтр", callback_data=ChatSettingsCallbackData(action=ChatSettingsAction.delete_filter, chat_id=chat_id))
    builder.button(text=toggle_text, callback_data=ChatSettingsCallbackData(action=ChatSettingsAction.toggle_active, chat_id=chat_id))
    builder.button(text="⚙️ Порог срабатывания", callback_data=ChatSettingsCallbackData(action=ChatSettingsAction.set_threshold, chat_id=chat_id))
    builder.button(text="🗑 Удалить чат из бота", callback_data=ChatSettingsCallbackData(action=ChatSettingsAction.delete_chat, chat_id=chat_id))  # <-- добавить
    builder.button(text="⬅️ Назад", callback_data=ChatSettingsCallbackData(action=ChatSettingsAction.back, chat_id=chat_id))
    builder.adjust(1)
    return builder.as_markup()


def filters_keyboard(chat_id: int, filters: list, page: int = 0, mode: str = "edit"):
    builder = InlineKeyboardBuilder()
    total = len(filters)
    total_pages = max(1, math.ceil(total / config.PAGE_SIZE))
    start = page * config.PAGE_SIZE
    end = start + config.PAGE_SIZE
    page_filters = filters[start:end]

    for f in page_filters:
        short = f.pattern[:35] + '...' if len(f.pattern) > 35 else f.pattern
        status = "✅" if f.is_active else "⏸"
        builder.button(
            text=f"{status} {short}",
            callback_data=FiltersCallbackData(
                action=FiltersAction.select,
                chat_id=chat_id,
                filter_id=f.id,
                page=page,
                mode=mode
            )
        )

    # Пагинация
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(("◀️", FiltersCallbackData(action=FiltersAction.page, chat_id=chat_id, filter_id=0, page=page - 1, mode=mode)))
        nav_buttons.append((f"{page + 1}/{total_pages}", FiltersCallbackData(action=FiltersAction.page, chat_id=chat_id, filter_id=0, page=page, mode=mode)))
        if page < total_pages - 1:
            nav_buttons.append(("▶️", FiltersCallbackData(action=FiltersAction.page, chat_id=chat_id, filter_id=0, page=page + 1, mode=mode)))
        for text, cd in nav_buttons:
            builder.button(text=text, callback_data=cd)
        builder.adjust(*([1] * len(page_filters)), len(nav_buttons))

    builder.button(
        text="⬅️ Назад",
        callback_data=FiltersCallbackData(action=FiltersAction.back, chat_id=chat_id, filter_id=0, page=0, mode=mode)
    )
    builder.adjust(1)
    return builder.as_markup()


def cancel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


def back_to_chat_keyboard(chat_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="⬅️ Назад к чату",
        callback_data=ChatSettingsCallbackData(action=ChatSettingsAction.back, chat_id=chat_id)
    )
    builder.adjust(1)
    return builder.as_markup()


def blocked_users_keyboard(users: list, page: int = 0):
    builder = InlineKeyboardBuilder()
    total = len(users)
    total_pages = max(1, math.ceil(total / config.PAGE_SIZE))
    start = page * config.PAGE_SIZE
    end = start + config.PAGE_SIZE
    page_users = users[start:end]

    for u in page_users:
        name = u.full_name or f"id{u.user_id}"
        builder.button(
            text=f"🚫 {name}",
            callback_data=BlockedCallbackData(action=BlockedAction.view, blocked_id=u.id, page=page)
        )

    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(("◀️", BlockedCallbackData(action=BlockedAction.page, page=page - 1)))
        nav.append((f"{page + 1}/{total_pages}", BlockedCallbackData(action=BlockedAction.page, page=page)))
        if page < total_pages - 1:
            nav.append(("▶️", BlockedCallbackData(action=BlockedAction.page, page=page + 1)))
        for text, cd in nav:
            builder.button(text=text, callback_data=cd)
        builder.adjust(*([1] * len(page_users)), len(nav))

    builder.button(text="⬅️ Назад", callback_data=BlockedCallbackData(action=BlockedAction.back))
    builder.adjust(1)
    return builder.as_markup()


def blocked_user_detail_keyboard(blocked_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Разблокировать", callback_data=BlockedCallbackData(action=BlockedAction.unban, blocked_id=blocked_id))
    builder.button(text="⬅️ Назад", callback_data=BlockedCallbackData(action=BlockedAction.back))
    builder.adjust(1)
    return builder.as_markup()