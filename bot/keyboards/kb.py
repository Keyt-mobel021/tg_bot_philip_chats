import math
from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards import *
import config


# ──────────────────────────────────────────────
#  Главное меню
# ──────────────────────────────────────────────
def main_menu_keyboard(is_admin_or_manager: bool = False):
    builder = InlineKeyboardBuilder()
    builder.button(text="💬 Чаты", callback_data=MainMenuCD(action=MainMenuAction.chats))
    if is_admin_or_manager:
        builder.button(text="👥 Сотрудники", callback_data=MainMenuCD(action=MainMenuAction.staff))
        builder.button(text="🔗 Автоподключение", callback_data=MainMenuCD(action=MainMenuAction.autoconnect))
        builder.button(text="🚫 Фильтры", callback_data=MainMenuCD(action=MainMenuAction.filters))
    builder.adjust(1)
    return builder.as_markup()


# ──────────────────────────────────────────────
#  Список чатов
# ──────────────────────────────────────────────
def chats_list_keyboard(chats: list, page: int = 0, can_create: bool = False):
    builder = InlineKeyboardBuilder()
    total = len(chats)
    total_pages = max(1, math.ceil(total / config.PAGE_SIZE))
    page_chats = chats[page * config.PAGE_SIZE:(page + 1) * config.PAGE_SIZE]

    for chat in page_chats:
        status = "❄️" if chat.is_frozen else "💬"
        builder.button(
            text=f"{status} {chat.title}",
            callback_data=ChatsCD(action=ChatsAction.select, chat_id=chat.id, page=page)
        )

    _add_pagination(builder, total_pages, page,
                    lambda p: ChatsCD(action=ChatsAction.page, page=p))

    if can_create:
        builder.button(text="➕ Создать чат", callback_data=ChatsCD(action=ChatsAction.create))

    builder.button(text="⬅️ Назад", callback_data=MainMenuCD(action=MainMenuAction.home))
    builder.adjust(1)
    return builder.as_markup()


# ──────────────────────────────────────────────
#  Детали чата
# ──────────────────────────────────────────────
def chat_detail_keyboard(chat_id: int, is_frozen: bool, is_admin_or_manager: bool):
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Написать сообщение",
                   callback_data=ChatCD(action=ChatAction.write, chat_id=chat_id))
    builder.button(text="📋 Посмотреть сообщения",
                   callback_data=ChatCD(action=ChatAction.history, chat_id=chat_id))

    if is_admin_or_manager:
        freeze_text = "🔥 Разморозить" if is_frozen else "❄️ Заморозить"
        builder.button(text=freeze_text,
                       callback_data=ChatCD(action=ChatAction.freeze, chat_id=chat_id))
        builder.button(text="👥 Участники",
                       callback_data=ChatCD(action=ChatAction.members, chat_id=chat_id))
        builder.button(text="📝 Описание чата",
                       callback_data=ChatCD(action=ChatAction.description, chat_id=chat_id))
        builder.button(text="🗑 Удалить чат",
                       callback_data=ChatCD(action=ChatAction.delete, chat_id=chat_id))
    else:
        builder.button(text="🚪 Выйти из чата",
                       callback_data=ChatCD(action=ChatAction.leave, chat_id=chat_id))

    builder.button(text="⬅️ Назад", callback_data=ChatsCD(action=ChatsAction.back))
    builder.adjust(1)
    return builder.as_markup()


def freeze_confirm_keyboard(chat_id: int, is_frozen: bool):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да", callback_data=ChatCD(action=ChatAction.freeze_confirm, chat_id=chat_id, page=1))
    builder.button(text="❌ Нет", callback_data=ChatCD(action=ChatAction.freeze_confirm, chat_id=chat_id, page=0))
    builder.adjust(2)
    return builder.as_markup()


def leave_confirm_keyboard(chat_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да", callback_data=ChatCD(action=ChatAction.leave_confirm, chat_id=chat_id, page=1))
    builder.button(text="❌ Нет", callback_data=ChatCD(action=ChatAction.leave_confirm, chat_id=chat_id, page=0))
    builder.adjust(2)
    return builder.as_markup()


# ──────────────────────────────────────────────
#  Описание чата (только для админов)
# ──────────────────────────────────────────────
def chat_description_keyboard(chat_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить описание",
                   callback_data=ChatCD(action=ChatAction.edit_description, chat_id=chat_id))
    builder.button(text="⬅️ Назад",
                   callback_data=ChatCD(action=ChatAction.back, chat_id=chat_id))
    builder.adjust(1)
    return builder.as_markup()


# ──────────────────────────────────────────────
#  История сообщений
# ──────────────────────────────────────────────
def history_keyboard(chat_id: int, page: int, total_pages: int):
    builder = InlineKeyboardBuilder()
    nav = []
    if page < total_pages - 1:
        nav.append(("⬅️ Старее", HistoryCD(action=HistoryAction.page, chat_id=chat_id, page=page + 1)))
    nav.append((f"стр. {page + 1}/{total_pages}", HistoryCD(action=HistoryAction.page, chat_id=chat_id, page=page)))
    if page > 0:
        nav.append(("Новее ➡️", HistoryCD(action=HistoryAction.page, chat_id=chat_id, page=page - 1)))
    for text, cd in nav:
        builder.button(text=text, callback_data=cd)
    if len(nav) > 0:
        builder.adjust(len(nav))
    builder.button(text="⬅️ Назад", callback_data=ChatCD(action=ChatAction.back, chat_id=chat_id))
    builder.adjust(1)
    return builder.as_markup()


# ──────────────────────────────────────────────
#  Кнопки под рассылкой
# ──────────────────────────────────────────────
def broadcast_reply_keyboard(chat_id: int):
    """Кнопки под входящим сообщением рассылки — быстрый ответ и история."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✏️ Ответить в чат",
        callback_data=ChatCD(action=ChatAction.write, chat_id=chat_id)
    )
    builder.button(
        text="📋 История сообщений",
        callback_data=ChatCD(action=ChatAction.history, chat_id=chat_id)
    )
    builder.adjust(1)
    return builder.as_markup()


# ──────────────────────────────────────────────
#  Участники
# ──────────────────────────────────────────────
def members_list_keyboard(members: list, chat_id: int, page: int = 0):
    builder = InlineKeyboardBuilder()
    total = len(members)
    total_pages = max(1, math.ceil(total / config.PAGE_SIZE))
    page_members = members[page * config.PAGE_SIZE:(page + 1) * config.PAGE_SIZE]

    for m in page_members:
        status = "🔒" if m.is_blocked else "👤"
        # В списке показываем display_name (с учётом alias)
        builder.button(
            text=f"{status} {m.display_name}",
            callback_data=MembersCD(action=MembersAction.select, chat_id=chat_id, member_id=m.id, page=page)
        )

    _add_pagination(builder, total_pages, page,
                    lambda p: MembersCD(action=MembersAction.page, chat_id=chat_id, page=p))

    builder.button(text="➕ Добавить участника",
                   callback_data=MembersCD(action=MembersAction.add, chat_id=chat_id))
    builder.button(text="⬅️ Назад",
                   callback_data=ChatCD(action=ChatAction.back, chat_id=chat_id))
    builder.adjust(1)
    return builder.as_markup()


def member_detail_keyboard(chat_id: int, member_id: int, is_blocked: bool, has_alias: bool = False):
    """
    Карточка участника — только для администратора.
    Кнопки: заморозить, редактировать тег, сбросить тег (если есть), удалить.
    """
    builder = InlineKeyboardBuilder()

    freeze_text = "🔥 Разморозить" if is_blocked else "❄️ Заморозить"
    builder.button(text=freeze_text,
                   callback_data=MembersCD(action=MembersAction.freeze, chat_id=chat_id, member_id=member_id))

    # Тег: кнопка редактирования всегда, кнопка сброса — только если тег задан
    alias_text = "✏️ Изменить тег" if has_alias else "🏷 Задать тег"
    builder.button(text=alias_text,
                   callback_data=MembersCD(action=MembersAction.edit_alias, chat_id=chat_id, member_id=member_id))
    if has_alias:
        builder.button(text="❌ Сбросить тег",
                       callback_data=MembersCD(action=MembersAction.clear_alias, chat_id=chat_id, member_id=member_id))

    builder.button(text="🗑 Удалить из чата",
                   callback_data=MembersCD(action=MembersAction.remove, chat_id=chat_id, member_id=member_id))
    builder.button(text="⬅️ Назад",
                   callback_data=MembersCD(action=MembersAction.list, chat_id=chat_id))
    builder.adjust(1)
    return builder.as_markup()


def member_freeze_confirm_keyboard(chat_id: int, member_id: int, is_blocked: bool):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да",
                   callback_data=MembersCD(action=MembersAction.freeze_confirm, chat_id=chat_id, member_id=member_id, page=1))
    builder.button(text="❌ Нет",
                   callback_data=MembersCD(action=MembersAction.freeze_confirm, chat_id=chat_id, member_id=member_id, page=0))
    builder.adjust(2)
    return builder.as_markup()


def member_remove_confirm_keyboard(chat_id: int, member_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да",
                   callback_data=MembersCD(action=MembersAction.remove_confirm, chat_id=chat_id, member_id=member_id, page=1))
    builder.button(text="❌ Нет",
                   callback_data=MembersCD(action=MembersAction.remove_confirm, chat_id=chat_id, member_id=member_id, page=0))
    builder.adjust(2)
    return builder.as_markup()


def add_member_keyboard(chat_id: int, profiles: list, users: list):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔗 Пригласить по ссылке",
                   callback_data=MembersCD(action=MembersAction.invite_link, chat_id=chat_id))
    for p in profiles:
        builder.button(
            text=f"👤 {p.name}" + (f" ({p.position})" if p.position else ""),
            callback_data=MembersCD(action=MembersAction.add_profile, chat_id=chat_id, profile_id=p.id)
        )
    builder.button(text="⬅️ Назад",
                   callback_data=MembersCD(action=MembersAction.list, chat_id=chat_id))
    builder.adjust(1)
    return builder.as_markup()


def invite_link_keyboard(chat_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Сбросить ссылку",
                   callback_data=MembersCD(action=MembersAction.reset_invite, chat_id=chat_id))
    builder.button(text="⬅️ Назад",
                   callback_data=MembersCD(action=MembersAction.list, chat_id=chat_id))
    builder.adjust(1)
    return builder.as_markup()


# ──────────────────────────────────────────────
#  Сотрудники
# ──────────────────────────────────────────────
def staff_list_keyboard(profiles: list, page: int = 0):
    builder = InlineKeyboardBuilder()
    total = len(profiles)
    total_pages = max(1, math.ceil(total / config.PAGE_SIZE))
    page_profiles = profiles[page * config.PAGE_SIZE:(page + 1) * config.PAGE_SIZE]

    for p in page_profiles:
        icon = "🔒" if p.is_blocked else "👤"
        builder.button(
            text=f"{icon} {p.name}",
            callback_data=StaffCD(action=StaffAction.select, profile_id=p.id, page=page)
        )

    _add_pagination(builder, total_pages, page,
                    lambda p_: StaffCD(action=StaffAction.page, page=p_))

    builder.button(text="➕ Добавить сотрудника",
                   callback_data=StaffCD(action=StaffAction.add))
    builder.button(text="⬅️ Назад", callback_data=MainMenuCD(action=MainMenuAction.chats))
    builder.adjust(1)
    return builder.as_markup()


def staff_detail_keyboard(profile_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Редактировать имя",
                   callback_data=StaffCD(action=StaffAction.edit_name, profile_id=profile_id))
    builder.button(text="✏️ Редактировать должность",
                   callback_data=StaffCD(action=StaffAction.edit_position, profile_id=profile_id))
    builder.button(text="🗑 Удалить сотрудника",
                   callback_data=StaffCD(action=StaffAction.delete, profile_id=profile_id))
    builder.button(text="⬅️ Назад",
                   callback_data=StaffCD(action=StaffAction.list))
    builder.adjust(1)
    return builder.as_markup()


def staff_delete_confirm_keyboard(profile_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да",
                   callback_data=StaffCD(action=StaffAction.delete_confirm, profile_id=profile_id, page=1))
    builder.button(text="❌ Нет",
                   callback_data=StaffCD(action=StaffAction.delete_confirm, profile_id=profile_id, page=0))
    builder.adjust(2)
    return builder.as_markup()


def profile_type_keyboard():
    from models import PROFILE_TYPES, PROFILE_TYPE_LABELS
    builder = InlineKeyboardBuilder()
    for pt in PROFILE_TYPES:
        builder.button(text=PROFILE_TYPE_LABELS[pt], callback_data=f"ptype:{pt}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


# ──────────────────────────────────────────────
#  Автоподключение
# ──────────────────────────────────────────────
def autoconnect_keyboard(auto_connects: list, profiles: list = None):
    builder = InlineKeyboardBuilder()
    for ac in auto_connects:
        try:
            p = ac.profile
            builder.button(
                text=f"❌ {p.name}",
                callback_data=AutoConnectCD(action=AutoConnectAction.delete, ac_id=ac.id)
            )
        except Exception:
            pass
    builder.button(text="➕ Добавить автоподключение",
                   callback_data=AutoConnectCD(action=AutoConnectAction.add))
    builder.button(text="⬅️ Назад", callback_data=MainMenuCD(action=MainMenuAction.chats))
    builder.adjust(1)
    return builder.as_markup()


def autoconnect_profile_keyboard(profiles: list):
    builder = InlineKeyboardBuilder()
    for p in profiles:
        builder.button(text=f"👤 {p.name}",
                       callback_data=AutoConnectCD(action=AutoConnectAction.add_profile, profile_id=p.id))
    builder.button(text="❌ Отмена", callback_data=AutoConnectCD(action=AutoConnectAction.back))
    builder.adjust(1)
    return builder.as_markup()


def autoconnect_delete_confirm_keyboard(ac_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да",
                   callback_data=AutoConnectCD(action=AutoConnectAction.delete_confirm, ac_id=ac_id))
    builder.button(text="❌ Нет",
                   callback_data=AutoConnectCD(action=AutoConnectAction.back))
    builder.adjust(2)
    return builder.as_markup()


# ──────────────────────────────────────────────
#  Фильтры
# ──────────────────────────────────────────────
def filters_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить фильтр",
                   callback_data=FiltersCD(action=FiltersAction.create_global))
    builder.button(text="⬅️ Назад", callback_data=MainMenuCD(action=MainMenuAction.chats))
    builder.adjust(1)
    return builder.as_markup()


def global_filters_keyboard(filters: list, page: int = 0):
    builder = InlineKeyboardBuilder()
    total = len(filters)
    total_pages = max(1, math.ceil(total / config.PAGE_SIZE))
    page_filters = filters[page * config.PAGE_SIZE:(page + 1) * config.PAGE_SIZE]
    for f in page_filters:
        short = f.pattern[:30] + '…' if len(f.pattern) > 30 else f.pattern
        status = "✅" if f.is_active else "⏸"
        builder.button(text=f"{status} {short}",
                       callback_data=FiltersCD(action=FiltersAction.select_global, filter_id=f.id, page=page))
    _add_pagination(builder, total_pages, page,
                    lambda p: FiltersCD(action=FiltersAction.page, page=p))
    builder.button(text="➕ Добавить фильтр",
                   callback_data=FiltersCD(action=FiltersAction.create_global))
    builder.button(text="⬅️ Назад",
                   callback_data=FiltersCD(action=FiltersAction.list))
    builder.adjust(1)
    return builder.as_markup()


def global_filter_detail_keyboard(filter_id: int, is_active: bool):
    builder = InlineKeyboardBuilder()
    toggle_text = "⏸ Деактивировать" if is_active else "▶️ Активировать"
    builder.button(text=toggle_text,
                   callback_data=FiltersCD(action=FiltersAction.toggle_global, filter_id=filter_id))
    builder.button(text="🗑 Удалить",
                   callback_data=FiltersCD(action=FiltersAction.delete_global, filter_id=filter_id))
    builder.button(text="⬅️ Назад",
                   callback_data=FiltersCD(action=FiltersAction.global_list))
    builder.adjust(1)
    return builder.as_markup()


def chat_filters_keyboard(filters: list, chat_id: int, page: int = 0):
    builder = InlineKeyboardBuilder()
    total = len(filters)
    total_pages = max(1, math.ceil(total / config.PAGE_SIZE))
    page_filters = filters[page * config.PAGE_SIZE:(page + 1) * config.PAGE_SIZE]
    for f in page_filters:
        short = f.pattern[:30] + '…' if len(f.pattern) > 30 else f.pattern
        status = "✅" if f.is_active else "⏸"
        builder.button(text=f"{status} {short}",
                       callback_data=FiltersCD(action=FiltersAction.select, filter_id=f.id, chat_id=chat_id, page=page))
    _add_pagination(builder, total_pages, page,
                    lambda p: FiltersCD(action=FiltersAction.page, chat_id=chat_id, page=p))
    builder.button(text="➕ Добавить фильтр",
                   callback_data=FiltersCD(action=FiltersAction.create, chat_id=chat_id))
    builder.button(text="⬅️ Назад",
                   callback_data=FiltersCD(action=FiltersAction.chat_list))
    builder.adjust(1)
    return builder.as_markup()


def chat_filter_detail_keyboard(filter_id: int, chat_id: int, is_active: bool):
    builder = InlineKeyboardBuilder()
    toggle_text = "⏸ Деактивировать" if is_active else "▶️ Активировать"
    builder.button(text=toggle_text,
                   callback_data=FiltersCD(action=FiltersAction.toggle, filter_id=filter_id, chat_id=chat_id))
    builder.button(text="🗑 Удалить",
                   callback_data=FiltersCD(action=FiltersAction.delete, filter_id=filter_id, chat_id=chat_id))
    builder.button(text="⬅️ Назад",
                   callback_data=FiltersCD(action=FiltersAction.chat_list))
    builder.adjust(1)
    return builder.as_markup()


def chats_for_filter_keyboard(chats: list):
    builder = InlineKeyboardBuilder()
    for chat in chats:
        builder.button(text=f"💬 {chat.title}",
                       callback_data=FiltersCD(action=FiltersAction.chat_list, chat_id=chat.id))
    builder.button(text="⬅️ Назад", callback_data=FiltersCD(action=FiltersAction.list))
    builder.adjust(1)
    return builder.as_markup()


# ──────────────────────────────────────────────
#  Уведомление о нарушении
# ──────────────────────────────────────────────
def violation_keyboard(member_id: int, profile_id: int, chat_id: int):
    builder = InlineKeyboardBuilder()
    if member_id:
        builder.button(text="🔓 Разморозить участника",
                       callback_data=ViolationCD(action=ViolationAction.unfreeze_member, member_id=member_id, chat_id=chat_id))
    if profile_id:
        builder.button(text="🔓 Разморозить профиль",
                       callback_data=ViolationCD(action=ViolationAction.unfreeze_profile, profile_id=profile_id, chat_id=chat_id))
    builder.adjust(1)
    return builder.as_markup()


# ──────────────────────────────────────────────
#  Утилита пагинации
# ──────────────────────────────────────────────
def _add_pagination(builder: InlineKeyboardBuilder, total_pages: int, page: int, cd_factory):
    if total_pages <= 1:
        return
    nav = []
    if page > 0:
        nav.append(("◀️", cd_factory(page - 1)))
    nav.append((f"стр. {page + 1}/{total_pages}", cd_factory(page)))
    if page < total_pages - 1:
        nav.append(("▶️", cd_factory(page + 1)))
    for text, cd in nav:
        builder.button(text=text, callback_data=cd)
    builder.adjust(1)


# ──────────────────────────────────────────────
#  Отмена / Общее
# ──────────────────────────────────────────────
def cancel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


def delete_chat_confirm_keyboard(chat_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить",
                   callback_data=ChatCD(action=ChatAction.delete_confirm, chat_id=chat_id, page=1))
    builder.button(text="❌ Нет",
                   callback_data=ChatCD(action=ChatAction.delete_confirm, chat_id=chat_id, page=0))
    builder.adjust(2)
    return builder.as_markup()