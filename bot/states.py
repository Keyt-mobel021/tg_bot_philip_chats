from aiogram.fsm.state import State, StatesGroup
 
 
# -=-=- Создание чата -=-=-
class ChatCreateState(StatesGroup):
    get_title = State()
    get_description = State()
 
 
# -=-=- ЗАДАЧА 5: Редактирование описания чата -=-=-
class ChatDescriptionEditState(StatesGroup):
    get_description = State()
 
 
# -=-=- Создание/редактирование профиля сотрудника -=-=-
class ProfileCreateState(StatesGroup):
    get_name = State()
    get_type = State()
    get_position = State()
 
 
class ProfileEditState(StatesGroup):
    get_name = State()
    get_position = State()
 
 
# -=-=- Отправка сообщения в чат -=-=-
class SendMessageState(StatesGroup):
    get_message = State()
 
 
# -=-=- Фильтры -=-=-
class FilterCreateState(StatesGroup):
    get_pattern = State()
    get_description = State()
 
 
class FilterEditState(StatesGroup):
    get_pattern = State()
 
 
# -=-=- Подтверждения -=-=-
class ConfirmState(StatesGroup):
    waiting = State()
