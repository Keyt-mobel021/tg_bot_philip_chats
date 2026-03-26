from aiogram import Dispatcher, Bot
import pickle

import models
import peewee
from loguru import logger



# -=-=- Подгружаем состояния и данные состояний -=-=-
async def get_data_states(dp: Dispatcher, bot: Bot):
    with models.connector:
        # try:
        users = models.UserTelegram.select()
        for itm in users:
            # -=-=- Синхронизируем состояние пользователя -=-=-
            state = dp.fsm.resolve_context(bot=bot, chat_id=itm.id, user_id=itm.id)
            # -=-=- Подгружаем состояния и данные состояния -=-=-
            
            # Берем сосотояния из базы
            try: data_state: models.DataState = models.DataState.get(models.DataState.user_id == itm.id)
            except peewee.DoesNotExist: data_state = None
            # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

            # Если состояния пустые но есть в базе
            if not (await state.get_data()) and not (await state.get_state()) and data_state:
                _data = pickle.loads(data_state.data)
                
                await state.set_state(state=data_state.state)
                await state.set_data(_data)
        
        # except Exception as _ex: logger.warning(f"Exception Loads States: {_ex}")
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=