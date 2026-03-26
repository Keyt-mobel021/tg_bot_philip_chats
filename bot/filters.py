import asyncio
from aiogram import types
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext

import datetime
import models
import text_templates
import config



LATENCY = 0.05  # секунды ожидания остальных частей медиагруппы

class PhotoFilter(BaseFilter):
    _album_data: dict[str, list[types.Message]] = {}

    async def __call__(self, message: types.Message) -> bool | dict:
        has_media = (
            message.photo or message.video or message.document or
            message.audio or message.voice or message.video_note or
            message.sticker
        )

        if not has_media:
            return False

        if not message.media_group_id:
            return {"album": [message]}

        gid = message.media_group_id

        try:
            self._album_data[gid].append(message)
            return False
        except KeyError:
            self._album_data[gid] = [message]
            await asyncio.sleep(LATENCY)
            album = self._album_data.pop(gid, [message])
            return {"album": album}



# -=-=- Фильтр Пользователя -=-=-
class CheckUser(BaseFilter):
    async def __call__(self, message: types.Message | types.CallbackQuery, state: FSMContext):
        if isinstance(message, types.CallbackQuery): message = message.message

        with models.connector:
            try:
                user = models.UserTelegram.get(models.UserTelegram.id == message.chat.id)
                user.full_name = message.chat.full_name
                user.appeal_time = datetime.datetime.now()
                user.username = message.chat.username
                user.save()
            except models.peewee.DoesNotExist:
                user = models.UserTelegram.create(id = message.chat.id,
                                          full_name = message.chat.full_name,
                                          username = message.chat.username,
                                          appeal_time = datetime.datetime.now(),
                                          date_create = datetime.datetime.now())
            
            # Ищем профиль
            profile = models.Profile.get_or_none(
                models.Profile.user_id == user
            )

            # Если is_admin и профиля нет — создаём автоматически
            if profile is None and user.is_admin:
                profile = models.Profile.create(
                    name=user.full_name or f"Admin {user.id}",
                    profile_type=models.ProfileType.ADMIN,
                    user_id=user.id,
                )

            # Проверяем блокировку
            if user.is_block or (profile and profile.is_blocked):
                await message.answer(text=text_templates.MESSAGE_BLOCK)
                return False
            
            is_admin_or_manager = profile is not None and profile.is_admin_or_manager

        return { 'user': user, 'profile': profile, 'is_admin_or_manager': is_admin_or_manager }
