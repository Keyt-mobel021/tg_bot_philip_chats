import datetime
from aiogram import Bot
from loguru import logger
import models


async def broadcast_message_to_chat(
    bot: Bot,
    chat: models.Chat,
    sender_member: models.ChatMember,
    text: str | None,
    attachments: list[models.Attachment] | None = None,
    exclude_member_id: int | None = None,
):
    """
    Рассылает сообщение всем незамороженным участникам чата.
    Формат: [Чат] Имя · дата/время + текст.
    ЗАДАЧА 1: добавляем кнопки «Ответить» и «История» под каждым сообщением.
    """
    from keyboards.kb import broadcast_reply_keyboard

    with models.connector:
        members = list(
            models.ChatMember.select()
            .where(
                (models.ChatMember.chat_id == chat.id) &
                (models.ChatMember.is_blocked == False)
            )
        )

    header = _build_header(sender_member, chat)
    full_text = f"{header}\n\n{text}" if text else header

    # Клавиатура с быстрыми действиями (ответить / история)
    reply_kb = broadcast_reply_keyboard(chat.id)

    for member in members:
        if member.id == exclude_member_id:
            continue
        if not member.user_id_id:
            continue

        try:
            if attachments:
                await _send_with_attachments(bot, member.user_id_id, full_text, attachments, reply_kb)
            else:
                await bot.send_message(
                    chat_id=member.user_id_id,
                    text=full_text,
                    parse_mode="HTML",
                    reply_markup=reply_kb,
                )
        except Exception as e:
            logger.warning(f"broadcast: failed to send to user {member.user_id_id}: {e}")


def _build_header(member: models.ChatMember, chat: models.Chat) -> str:
    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    name = member.display_name
    return f"💬 <b>{chat.title}</b>\n👤 {name} · {now}"


async def _send_with_attachments(
    bot: Bot,
    user_id: int,
    caption: str,
    attachments: list[models.Attachment],
    reply_markup=None,
):
    from aiogram.types import (
        InputMediaPhoto, InputMediaVideo,
        InputMediaDocument, InputMediaAudio,
    )

    # Одно вложение — отправляем с caption
    if len(attachments) == 1:
        await _send_single(bot, user_id, attachments[0], caption, reply_markup=reply_markup)
        return

    # Медиагруппа только для фото/видео, остальное отдельно
    media_group = []
    non_media = []

    for i, a in enumerate(attachments):
        if a.attachment_type == models.AttachmentType.PHOTO:
            media_group.append(InputMediaPhoto(
                media=a.id_file,
                caption=caption if i == 0 else None,
                parse_mode="HTML" if i == 0 else None,
            ))
        elif a.attachment_type == models.AttachmentType.VIDEO:
            media_group.append(InputMediaVideo(
                media=a.id_file,
                caption=caption if i == 0 else None,
                parse_mode="HTML" if i == 0 else None,
            ))
        else:
            non_media.append(a)

    if media_group:
        sent = await bot.send_media_group(chat_id=user_id, media=media_group)
        # Кнопки добавляем отдельным сообщением после медиагруппы
        if reply_markup and sent:
            await bot.send_message(
                chat_id=user_id,
                text="👆 Сообщение выше",
                reply_markup=reply_markup,
            )

    for a in non_media:
        # caption уже ушёл с медиагруппой — не дублируем
        await _send_single(
            bot, user_id, a,
            caption if not media_group else None,
            reply_markup=reply_markup if not media_group else None,
        )


async def _send_single(
    bot: Bot,
    user_id: int,
    attachment: models.Attachment,
    caption: str | None,
    reply_markup=None,
):
    t = attachment.attachment_type
    kwargs = {"chat_id": user_id}
    if caption:
        kwargs["caption"] = caption
        kwargs["parse_mode"] = "HTML"
    if reply_markup:
        kwargs["reply_markup"] = reply_markup

    if t == models.AttachmentType.PHOTO:
        await bot.send_photo(photo=attachment.id_file, **kwargs)
    elif t == models.AttachmentType.VIDEO:
        await bot.send_video(video=attachment.id_file, **kwargs)
    elif t == models.AttachmentType.AUDIO:
        await bot.send_audio(audio=attachment.id_file, **kwargs)
    elif t == models.AttachmentType.VOICE:
        await bot.send_voice(voice=attachment.id_file, **kwargs)
    elif t == models.AttachmentType.VIDEO_NOTE:
        # video_note не поддерживает caption
        await bot.send_video_note(video_note=attachment.id_file, chat_id=user_id)
        if reply_markup:
            await bot.send_message(chat_id=user_id, text="👆", reply_markup=reply_markup)
    else:
        await bot.send_document(document=attachment.id_file, **kwargs)


async def notify_admins_violation(
    bot: Bot,
    chat: models.Chat,
    sender_member: models.ChatMember,
    text: str,
):
    """
    Уведомляет администраторов и руководителей чата о нарушении фильтра.
    """
    from keyboards.kb import violation_keyboard

    with models.connector:
        admin_members = list(
            models.ChatMember.select()
            .where(
                (models.ChatMember.chat_id == chat.id) &
                (models.ChatMember.member_type.in_([
                    models.MemberType.ADMIN, models.MemberType.MANAGER,
                ]))
            )
        )

    profile_id = sender_member.profile_id_id or 0
    name = sender_member.display_name

    notify_text = (
        f"🚨 <b>Нарушение фильтра</b>\n\n"
        f"💬 Чат: <b>{chat.title}</b>\n"
        f"👤 Участник: <b>{name}</b>\n"
        f"📝 Сообщение:\n<blockquote>{text[:400]}</blockquote>"
    )

    kb = violation_keyboard(
        member_id=sender_member.id,
        profile_id=profile_id,
        chat_id=chat.id,
    )

    admin_user_ids = [m.user_id_id for m in admin_members if m.user_id_id]

    if not admin_user_ids:
        with models.connector:
            global_admins = list(
                models.UserTelegram.select().where(models.UserTelegram.is_admin == True)
            )
        admin_user_ids = [u.id for u in global_admins]

    for uid in admin_user_ids:
        try:
            await bot.send_message(
                chat_id=uid,
                text=notify_text,
                reply_markup=kb,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"notify_admins: failed to send to {uid}: {e}")