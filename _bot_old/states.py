from aiogram.fsm.state import State, StatesGroup


class FilterCreateState(StatesGroup):
    get_pattern = State()


class FilterEditState(StatesGroup):
    get_pattern = State()


class ThresholdState(StatesGroup):
    get_threshold = State()
