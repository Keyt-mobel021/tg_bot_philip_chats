from aiogram.filters.callback_data import CallbackData
from enum import Enum


from aiogram.filters.callback_data import CallbackData
from enum import Enum


# ══════════════════════════════════════════════
#  Главное меню
# ══════════════════════════════════════════════
class MainMenuAction(str, Enum):
    chats = "chats"
    staff = "staff"
    autoconnect = "autoconnect"
    filters = "filters"
    home = "home"

class MainMenuCD(CallbackData, prefix="mm"):
    action: MainMenuAction


# ══════════════════════════════════════════════
#  Список чатов
# ══════════════════════════════════════════════
class ChatsAction(str, Enum):
    select = "select"
    page = "page"
    create = "create"
    back = "back"

class ChatsCD(CallbackData, prefix="chats"):
    action: ChatsAction
    chat_id: int = 0
    page: int = 0


# ══════════════════════════════════════════════
#  Действия в чате
# ══════════════════════════════════════════════
class ChatAction(str, Enum):
    write = "write"
    history = "history"
    freeze = "freeze"
    freeze_confirm = "freeze_confirm"
    members = "members"
    leave = "leave"
    leave_confirm = "leave_confirm"
    back = "back"
    delete = "delete"
    delete_confirm = "delete_confirm"
    # ЗАДАЧА 5: просмотр и редактирование описания (только для админов)
    description = "description"
    edit_description = "edit_description"

class ChatCD(CallbackData, prefix="chat"):
    action: ChatAction
    chat_id: int
    page: int = 0


# ══════════════════════════════════════════════
#  История сообщений
# ══════════════════════════════════════════════
class HistoryAction(str, Enum):
    page = "page"
    back = "back"

class HistoryCD(CallbackData, prefix="hist"):
    action: HistoryAction
    chat_id: int
    page: int = 0


# ══════════════════════════════════════════════
#  Участники чата
# ══════════════════════════════════════════════
class MembersAction(str, Enum):
    list = "list"
    select = "select"
    add = "add"
    add_profile = "add_profile"
    invite_link = "invite_link"
    remove = "remove"
    remove_confirm = "remove_confirm"
    freeze = "freeze"
    freeze_confirm = "freeze_confirm"
    page = "page"
    back = "back"

class MembersCD(CallbackData, prefix="mbr"):
    action: MembersAction
    chat_id: int
    member_id: int = 0
    profile_id: int = 0
    page: int = 0


# ══════════════════════════════════════════════
#  Сотрудники (профили)
# ══════════════════════════════════════════════
class StaffAction(str, Enum):
    list = "list"
    select = "select"
    add = "add"
    edit_name = "edit_name"
    edit_position = "edit_position"
    delete = "delete"
    delete_confirm = "delete_confirm"
    page = "page"
    back = "back"

class StaffCD(CallbackData, prefix="staff"):
    action: StaffAction
    profile_id: int = 0
    page: int = 0


# ══════════════════════════════════════════════
#  Автоподключение
# ══════════════════════════════════════════════
class AutoConnectAction(str, Enum):
    list = "list"
    add = "add"
    add_profile = "add_profile"
    delete = "delete"
    delete_confirm = "delete_confirm"
    back = "back"

class AutoConnectCD(CallbackData, prefix="ac"):
    action: AutoConnectAction
    ac_id: int = 0
    profile_id: int = 0


# ══════════════════════════════════════════════
#  Фильтры
# ══════════════════════════════════════════════
class FiltersAction(str, Enum):
    list = "list"
    global_list = "global_list"
    chat_list = "chat_list"
    select = "select"
    select_global = "select_global"
    create = "create"
    create_global = "create_global"
    toggle = "toggle"
    toggle_global = "toggle_global"
    delete = "delete"
    delete_global = "delete_global"
    page = "page"
    back = "back"

class FiltersCD(CallbackData, prefix="flt"):
    action: FiltersAction
    chat_id: int = 0
    filter_id: int = 0
    page: int = 0


# ══════════════════════════════════════════════
#  Уведомления о нарушениях (для администраторов)
# ══════════════════════════════════════════════
class ViolationAction(str, Enum):
    unfreeze_member = "unfreeze_member"
    unfreeze_profile = "unfreeze_profile"

class ViolationCD(CallbackData, prefix="viol"):
    action: ViolationAction
    member_id: int = 0
    profile_id: int = 0
    chat_id: int = 0