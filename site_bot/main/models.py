from django.db import models
from django.utils.html import format_html
import secrets


# ══════════════════════════════════════════════
#  Telegram пользователь
# ══════════════════════════════════════════════
class UserTelegram(models.Model):
    id = models.BigIntegerField("Id пользователя", primary_key=True, unique=True)
    full_name = models.CharField("Имя", max_length=255, null=True, blank=True)
    username = models.CharField("Юзернэйм", max_length=255, null=True, blank=True)
    appeal_time = models.DateTimeField("Дата последнего обращения")
    is_admin = models.BooleanField("Администратор", default=False)
    is_block = models.BooleanField("Блокировка", default=False)
    date_create = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        verbose_name = "Telegram Пользователь"
        verbose_name_plural = "Telegram Пользователи"

    def __str__(self):
        return f"{self.id} — {self.full_name or '—'}"

    def user_html(self):
        if self.username:
            return format_html(
                '<a href="https://t.me/{0}">https://t.me/{0}</a>',
                self.username,
            )
        return "—"

    user_html.short_description = "Ссылка на Telegram"


# ══════════════════════════════════════════════
#  Данные состояний (FSM)
# ══════════════════════════════════════════════
class DataState(models.Model):
    user = models.OneToOneField(
        UserTelegram,
        verbose_name="Пользователь",
        related_name="data_state",
        on_delete=models.CASCADE,
    )
    state = models.CharField("Состояние", max_length=255, null=True, blank=True)
    data = models.BinaryField("Данные состояния", null=True, blank=True)

    class Meta:
        verbose_name = "Состояние пользователя"
        verbose_name_plural = "Состояния пользователей"

    def __str__(self):
        return f"{self.user} — {self.state or '—'}"


# ══════════════════════════════════════════════
#  Профиль (системная роль компании)
# ══════════════════════════════════════════════
PROFILE_TYPE_ADMIN = 'admin'
PROFILE_TYPE_MANAGER = 'manager'
PROFILE_TYPE_EMPLOYEE = 'employee'

PROFILE_TYPE_CHOICES = [
    (PROFILE_TYPE_ADMIN, 'Администратор'),
    (PROFILE_TYPE_MANAGER, 'Руководитель'),
    (PROFILE_TYPE_EMPLOYEE, 'Сотрудник'),
]


def _generate_token():
    return secrets.token_urlsafe(32)


class Profile(models.Model):
    name = models.CharField("Имя", max_length=255)
    profile_type = models.CharField(
        "Тип профиля",
        max_length=50,
        choices=PROFILE_TYPE_CHOICES,
        default=PROFILE_TYPE_EMPLOYEE,
    )
    user = models.ForeignKey(
        UserTelegram,
        verbose_name="Telegram аккаунт",
        null=True,
        blank=True,
        related_name="profiles",
        on_delete=models.SET_NULL,
    )
    connect_token = models.CharField(
        "Токен подключения",
        max_length=64,
        unique=True,
        default=_generate_token,
    )
    position = models.CharField("Должность", max_length=255, null=True, blank=True)
    is_blocked = models.BooleanField("Заблокирован", default=False)
    date_create = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        verbose_name = "Профиль"
        verbose_name_plural = "Профили"

    def __str__(self):
        return f"{self.name} ({self.get_profile_type_display()})"

    @property
    def type_label(self):
        return self.get_profile_type_display()

    @property
    def is_admin_or_manager(self):
        return self.profile_type in (PROFILE_TYPE_ADMIN, PROFILE_TYPE_MANAGER)

    def connect_link_html(self):
        from django.conf import settings
        bot_username = getattr(settings, 'BOT_USERNAME', '')
        if bot_username and not self.user:
            url = f"https://t.me/{bot_username}?start=pe_{self.connect_token}"
            return format_html('<a href="{0}">{0}</a>', url)
        return "—"

    connect_link_html.short_description = "Ссылка для подключения"


# ══════════════════════════════════════════════
#  Чат
# ══════════════════════════════════════════════
class Chat(models.Model):
    title = models.CharField("Название", max_length=255)
    description = models.TextField("Описание", null=True, blank=True)
    is_visible = models.BooleanField("Видимый", default=True)
    is_frozen = models.BooleanField("Заморожен", default=False)
    creator = models.ForeignKey(
        Profile,
        verbose_name="Создатель",
        null=True,
        blank=True,
        related_name="created_chats",
        on_delete=models.SET_NULL,
    )
    date_create = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        verbose_name = "Чат"
        verbose_name_plural = "Чаты"

    def __str__(self):
        return self.title

    def members_count(self):
        return self.members.count()

    members_count.short_description = "Участников"


# ══════════════════════════════════════════════
#  Участник чата
# ══════════════════════════════════════════════
MEMBER_TYPE_CLIENT = 'client'
MEMBER_TYPE_ADMIN = 'admin'
MEMBER_TYPE_MANAGER = 'manager'
MEMBER_TYPE_EMPLOYEE = 'employee'

MEMBER_TYPE_CHOICES = [
    (MEMBER_TYPE_CLIENT, 'Клиент'),
    (MEMBER_TYPE_ADMIN, 'Администратор'),
    (MEMBER_TYPE_MANAGER, 'Руководитель'),
    (MEMBER_TYPE_EMPLOYEE, 'Сотрудник'),
]


def _generate_member_token():
    return secrets.token_urlsafe(32)


class ChatMember(models.Model):
    chat = models.ForeignKey(
        Chat,
        verbose_name="Чат",
        related_name="members",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        UserTelegram,
        verbose_name="Telegram пользователь",
        null=True,
        blank=True,
        related_name="memberships",
        on_delete=models.SET_NULL,
    )
    profile = models.ForeignKey(
        Profile,
        verbose_name="Профиль",
        null=True,
        blank=True,
        related_name="memberships",
        on_delete=models.SET_NULL,
    )
    connect_token = models.CharField(
        "Токен подключения",
        max_length=64,
        unique=True,
        default=_generate_member_token,
    )
    member_type = models.CharField(
        "Тип участника",
        max_length=50,
        choices=MEMBER_TYPE_CHOICES,
        default=MEMBER_TYPE_CLIENT,
    )
    is_blocked = models.BooleanField("Заморожен", default=False)
    
    alias = models.CharField("Тег участника", max_length=100, null=True, blank=True)
    date_create = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        verbose_name = "Участник чата"
        verbose_name_plural = "Участники чатов"

    def __str__(self):
        return f"{self.display_name} в «{self.chat}»"

    @property
    def display_name(self):
        if self.profile:
            p = self.profile
            parts = []
            if p.position:
                parts.append(p.position)
            parts.append(p.name)
            return ' — '.join(parts) if len(parts) > 1 else parts[0]
        if self.user:
            u = self.user
            return u.full_name or f"tg:{u.id}"
        return "Неизвестный"

    @property
    def type_label(self):
        return self.get_member_type_display()

    @property
    def is_admin_or_manager(self):
        return self.member_type in (MEMBER_TYPE_ADMIN, MEMBER_TYPE_MANAGER)


# ══════════════════════════════════════════════
#  Сообщение
# ══════════════════════════════════════════════
class Message(models.Model):
    member = models.ForeignKey(
        ChatMember,
        verbose_name="Участник",
        related_name="messages",
        on_delete=models.CASCADE,
    )
    text = models.TextField("Текст", null=True, blank=True)
    has_forbidden = models.BooleanField("Содержит запрещённые материалы", default=False)
    date_create = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"

    def __str__(self):
        preview = (self.text or '')[:50]
        return f"Сообщение #{self.id} — {self.member}: {preview}"


# ══════════════════════════════════════════════
#  Вложение
# ══════════════════════════════════════════════
ATTACHMENT_PHOTO = 'photo'
ATTACHMENT_VIDEO = 'video'
ATTACHMENT_AUDIO = 'audio'
ATTACHMENT_VOICE = 'voice'
ATTACHMENT_DOCUMENT = 'document'
ATTACHMENT_VIDEO_NOTE = 'video_note'
ATTACHMENT_STICKER = 'sticker'

ATTACHMENT_TYPE_CHOICES = [
    (ATTACHMENT_PHOTO, 'Фото'),
    (ATTACHMENT_VIDEO, 'Видео'),
    (ATTACHMENT_AUDIO, 'Аудио'),
    (ATTACHMENT_VOICE, 'Голосовое'),
    (ATTACHMENT_DOCUMENT, 'Документ'),
    (ATTACHMENT_VIDEO_NOTE, 'Видеокружок'),
    (ATTACHMENT_STICKER, 'Стикер'),
]


class Attachment(models.Model):
    message = models.ForeignKey(
        Message,
        verbose_name="Сообщение",
        related_name="attachments",
        on_delete=models.CASCADE,
    )
    id_file = models.CharField("File ID (Telegram)", max_length=512)
    attachment_type = models.CharField(
        "Тип вложения",
        max_length=50,
        choices=ATTACHMENT_TYPE_CHOICES,
        default=ATTACHMENT_DOCUMENT,
    )
    date_create = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        verbose_name = "Вложение"
        verbose_name_plural = "Вложения"

    def __str__(self):
        return f"{self.get_attachment_type_display()} к сообщению #{self.message}"


# ══════════════════════════════════════════════
#  Автоподключение
# ══════════════════════════════════════════════
class AutoConnect(models.Model):
    profile = models.ForeignKey(
        Profile,
        verbose_name="Профиль",
        related_name="auto_connects",
        on_delete=models.CASCADE,
    )
    date_create = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        verbose_name = "Автоподключение"
        verbose_name_plural = "Автоподключения"

    def __str__(self):
        return f"Автоподключение: {self.profile}"


# ══════════════════════════════════════════════
#  Фильтр по чату
# ══════════════════════════════════════════════
class ChatFilter(models.Model):
    chat = models.ForeignKey(
        Chat,
        verbose_name="Чат",
        related_name="filters",
        on_delete=models.CASCADE,
    )
    pattern = models.TextField("Паттерн (regex)")
    description = models.CharField("Описание", max_length=255, null=True, blank=True)
    is_active = models.BooleanField("Активен", default=True)
    date_create = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        verbose_name = "Фильтр чата"
        verbose_name_plural = "Фильтры чатов"

    def __str__(self):
        short = self.pattern[:40] + '...' if len(self.pattern) > 40 else self.pattern
        return f"[{self.chat}] {short}"


# ══════════════════════════════════════════════
#  Глобальный фильтр
# ══════════════════════════════════════════════
class GlobalFilter(models.Model):
    pattern = models.TextField("Паттерн (regex)")
    description = models.CharField("Описание", max_length=255, null=True, blank=True)
    is_active = models.BooleanField("Активен", default=True)
    date_create = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        verbose_name = "Глобальный фильтр"
        verbose_name_plural = "Глобальные фильтры"

    def __str__(self):
        short = self.pattern[:40] + '...' if len(self.pattern) > 40 else self.pattern
        return short