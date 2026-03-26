from aiogram.filters.callback_data import CallbackData
from enum import Enum


# -=-=- Главное меню -=-=-
class MenuAction(str, Enum):
    chats = "chats"
    blocked = "blocked"

class MenuCallbackData(CallbackData, prefix="menu"):
    action: MenuAction


# -=-=- Список чатов (с пагинацией) -=-=-
class ChatsAction(str, Enum):
    select = "select"
    page = "page"
    back = "back"

class ChatsCallbackData(CallbackData, prefix="chats"):
    action: ChatsAction
    chat_id: int = 0
    page: int = 0


# -=-=- Настройки конкретного чата -=-=-
class ChatSettingsAction(str, Enum):
    create_filter = "create_filter"
    edit_filter = "edit_filter"
    delete_filter = "delete_filter"
    toggle_active = "toggle_active"
    set_threshold = "set_threshold"
    delete_chat = "delete_chat"
    back = "back"

class ChatSettingsCallbackData(CallbackData, prefix="chat_settings"):
    action: ChatSettingsAction
    chat_id: int


# -=-=- Список фильтров (с пагинацией) -=-=-
class FiltersAction(str, Enum):
    select = "select"
    page = "page"
    back = "back"

class FiltersCallbackData(CallbackData, prefix="filters"):
    action: FiltersAction
    chat_id: int
    filter_id: int = 0
    page: int = 0
    mode: str = "edit"  # "edit" или "delete"


# -=-=- Заблокированные пользователи -=-=-
class BlockedAction(str, Enum):
    list = "list"
    view = "view"
    unban = "unban"
    page = "page"
    back = "back"

class BlockedCallbackData(CallbackData, prefix="blocked"):
    action: BlockedAction
    blocked_id: int = 0
    page: int = 0