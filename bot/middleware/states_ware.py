from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.fsm.context import FSMContext
from typing import Any, Awaitable, Callable, Dict, TypeVar
from aiogram import types
import json
import models
import peewee
import ast
import states
import pickle
import dill


def filter_serializable(data):
    """ Фильтрация несериализуемых объектов, таких как contextvars. """
    serializable_data = {}
    for key, value in data.items():
        try:
            dill.dumps(value)
            serializable_data[key] = value
        except Exception:
            print(f"Невозможно сериализовать: {key} ({type(value)})")
    return serializable_data


# -=-=- Миделваре пост обработки Message -=-=-
class SaveStateMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[types.Message | types.CallbackQuery, Dict[str, Any]], Awaitable[Any]],
            event: types.Message | types.CallbackQuery,
            data: Dict[str, Any],
        ):
        
        # Выполняем Хэндлер
        await handler(event, data)


        message = event
        # message = event.message
        if isinstance(event, types.CallbackQuery): message = event.message
        state: FSMContext | None = data.get('state', None)
        # types.Message().model_validate_json()
        # print(message.model_dump_json())
        

        # -=-=- Сохраняем состояния и данные состояния -=-=-
        with models.connector:
            # Берем сосотояния из базы
            try: data_state: models.DataState = models.DataState.get(models.DataState.user_id == message.chat.id)
            except peewee.DoesNotExist: data_state = None
            
            __state = (await state.get_state())
            # Фильтрация данных
            __data = dill.dumps(filter_serializable((await state.get_data())))
            # __data = pickle.dumps((await state.get_data()))

            # Сохроняем состояния
            if not data_state:
                try: models.DataState.create(user_id = message.chat.id,
                                            state = __state,
                                            data = __data)
                except peewee.DoesNotExist: pass
            else:
                try:
                    data_state.state = __state
                    data_state.data = __data
                    data_state.save()
                except peewee.DoesNotExist: pass
        # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
