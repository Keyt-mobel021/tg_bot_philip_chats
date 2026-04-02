"""
Менеджер активных сессий чата.
Хранит в памяти информацию о том, какой пользователь сейчас
находится в сессии какого чата, и message_id его сообщения с историей.
"""

# { user_tg_id: { "chat_id": int, "history_msg_id": int, "info_msg_id": int } }
active_sessions: dict[int, dict] = {}


def enter_session(user_tg_id: int, chat_id: int, history_msg_id: int, info_msg_id: int):
    active_sessions[user_tg_id] = {
        "chat_id": chat_id,
        "history_msg_id": history_msg_id,
        "info_msg_id": info_msg_id,
    }


def leave_session(user_tg_id: int):
    active_sessions.pop(user_tg_id, None)


def get_session(user_tg_id: int) -> dict | None:
    return active_sessions.get(user_tg_id)


def is_in_session(user_tg_id: int, chat_id: int) -> bool:
    """Проверяет, находится ли пользователь в сессии конкретного чата."""
    s = active_sessions.get(user_tg_id)
    return s is not None and s["chat_id"] == chat_id


def get_users_in_chat_session(chat_id: int) -> list[int]:
    """Возвращает список user_tg_id, которые сейчас в сессии данного чата."""
    return [
        uid for uid, data in active_sessions.items()
        if data["chat_id"] == chat_id
    ]