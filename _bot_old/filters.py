from aiogram import types
from aiogram.filters import BaseFilter
import models
import config


class CheckAdmin(BaseFilter):
    """Проверяет является ли пользователь администратором бота"""

    async def __call__(self, event: types.Message | types.CallbackQuery) -> bool | dict:
        user_id = event.from_user.id

        if user_id in config.ADMIN_IDS:
            # Сохраняем в базу если ещё нет
            with models.connector:
                if not models.AdminUser.get_or_none(models.AdminUser.id == user_id):
                    models.AdminUser.create(
                        id=user_id,
                        full_name=event.from_user.full_name,
                        username=event.from_user.username,
                    )
            return True

        with models.connector:
            admin = models.AdminUser.get_or_none(models.AdminUser.id == user_id)
            return admin is not None