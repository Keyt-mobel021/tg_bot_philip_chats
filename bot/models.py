import peewee
import datetime
import secrets

# connector = peewee.SqliteDatabase('E:\\1Work\\tg_bot_philip_chats\\site_bot\\db.sqlite3')
connector = peewee.SqliteDatabase('/var/www/site_bot/db.sqlite3')


class BaseModel(peewee.Model):
    class Meta:
        database = connector


# -=-=- Telegram пользователь -=-=-
class UserTelegram(BaseModel):
    # Id Telegram
    id = peewee.BigIntegerField(unique=True, primary_key=True)
    # Имя Telegram
    full_name = peewee.CharField(max_length=255, null=True)
    # Username
    username = peewee.CharField(max_length=255, null=True)
    # Последняя активность пользователя
    appeal_time = peewee.DateTimeField()
    # Администратор
    is_admin = peewee.BooleanField(default=False)
    # Блокировка пользователя
    is_block = peewee.BooleanField(default=False)
    # Дата создания
    date_create = peewee.DateTimeField()

    class Meta:
        table_name = 'main_usertelegram'

    def __str__(self):
        return self.full_name or str(self.id)


# -=-=- Модель Данных состояний -=-=-
class DataState(peewee.Model):
    id = peewee.IntegerField(unique=True, primary_key=True, index=True)
    # Пользователь
    user_id = peewee.ForeignKeyField(UserTelegram, related_name='data_state', on_delete="CASCADE")
    # Состояние
    state = peewee.CharField(max_length=255, null=True)
    # Данные состояния
    data = peewee.BlobField(null=True)

    class Meta:
        database = connector
        table_name = 'main_datastate'




# -=-=- Профиль (системная роль компании) -=-=-
class ProfileType(str):
    ADMIN = 'admin'
    MANAGER = 'manager'
    EMPLOYEE = 'employee'
 
PROFILE_TYPES = [ProfileType.ADMIN, ProfileType.MANAGER, ProfileType.EMPLOYEE]
PROFILE_TYPE_LABELS = {
    ProfileType.ADMIN: 'Администратор',
    ProfileType.MANAGER: 'Руководитель',
    ProfileType.EMPLOYEE: 'Сотрудник',
}
 
 
class Profile(BaseModel):
    id = peewee.AutoField(primary_key=True)
    name = peewee.CharField(max_length=255)
    profile_type = peewee.CharField(max_length=50, default=ProfileType.EMPLOYEE)
    user_id = peewee.ForeignKeyField(UserTelegram, null=True, backref='profiles', on_delete='SET NULL')
    connect_token = peewee.CharField(max_length=64, unique=True, default=lambda: secrets.token_urlsafe(32))
    position = peewee.CharField(max_length=255, null=True)
    is_blocked = peewee.BooleanField(default=False)
    date_create = peewee.DateTimeField(default=datetime.datetime.now)
 
    class Meta:
        table_name = 'main_profile'
 
    def __str__(self):
        return self.name
 
    @property
    def type_label(self):
        return PROFILE_TYPE_LABELS.get(self.profile_type, self.profile_type)
 
    @property
    def is_admin_or_manager(self):
        return self.profile_type in (ProfileType.ADMIN, ProfileType.MANAGER)
 
 
# -=-=- Чат -=-=-
class Chat(BaseModel):
    id = peewee.AutoField(primary_key=True)
    title = peewee.CharField(max_length=255)
    description = peewee.TextField(null=True)
    is_visible = peewee.BooleanField(default=True)
    is_frozen = peewee.BooleanField(default=False)
    creator_id = peewee.ForeignKeyField(Profile, null=True, backref='created_chats', on_delete='SET NULL')
    date_create = peewee.DateTimeField(default=datetime.datetime.now)
 
    class Meta:
        table_name = 'main_chat'
 
    def __str__(self):
        return self.title
 
 
# -=-=- Тип участника чата -=-=-
class MemberType(str):
    CLIENT = 'client'
    ADMIN = 'admin'
    MANAGER = 'manager'
    EMPLOYEE = 'employee'
 
MEMBER_TYPES = [MemberType.CLIENT, MemberType.ADMIN, MemberType.MANAGER, MemberType.EMPLOYEE]
MEMBER_TYPE_LABELS = {
    MemberType.CLIENT: 'Клиент',
    MemberType.ADMIN: 'Администратор',
    MemberType.MANAGER: 'Руководитель',
    MemberType.EMPLOYEE: 'Сотрудник',
}
 
 
class ChatMember(BaseModel):
    id = peewee.AutoField(primary_key=True)
    chat_id = peewee.ForeignKeyField(Chat, backref='members', on_delete='CASCADE')
    user_id = peewee.ForeignKeyField(UserTelegram, null=True, backref='memberships', on_delete='SET NULL')
    profile_id = peewee.ForeignKeyField(Profile, null=True, backref='memberships', on_delete='SET NULL')
    connect_token = peewee.CharField(max_length=64, unique=True, default=lambda: secrets.token_urlsafe(32))
    member_type = peewee.CharField(max_length=50, default=MemberType.CLIENT)
    is_blocked = peewee.BooleanField(default=False)
    # ── Тег/псевдоним участника ────────────────────────────────────────────────
    # Задаётся только администратором чата.
    # Используется вместо реального имени везде в рассылках и истории сообщений.
    # Реальное имя (_real_name) видно только админу/руководителю в карточке.
    alias = peewee.CharField(max_length=100, null=True)
    date_create = peewee.DateTimeField(default=datetime.datetime.now)
 
    class Meta:
        table_name = 'main_chatmember'
 
    @property
    def display_name(self) -> str:
        """
        Публичное имя — то, что видят ВСЕ участники в рассылках и истории.
        Если задан alias — используется он. Иначе — реальное имя.
        """
        if self.alias:
            return self.alias
        return self._real_name
 
    @property
    def _real_name(self) -> str:
        """
        Реальное имя участника без учёта alias.
        Показывается только администраторам в карточке участника.
        """
        if self.profile_id:
            p = self.profile_id
            parts = []
            if p.position:
                parts.append(p.position)
            parts.append(p.name)
            return ' — '.join(parts) if len(parts) > 1 else parts[0]
        if self.user_id:
            u = self.user_id
            return u.full_name or f"tg:{u.id}"
        return "Неизвестный"
 
    @property
    def type_label(self):
        return MEMBER_TYPE_LABELS.get(self.member_type, self.member_type)
 
    @property
    def is_admin_or_manager(self):
        return self.member_type in (MemberType.ADMIN, MemberType.MANAGER)
 
 
# -=-=- Многоразовая ссылка-приглашение в чат -=-=-
class ChatInviteLink(BaseModel):
    id = peewee.AutoField(primary_key=True)
    chat_id = peewee.ForeignKeyField(Chat, backref='invite_links', on_delete='CASCADE')
    token = peewee.CharField(max_length=64, unique=True)
    is_active = peewee.BooleanField(default=True)
    date_create = peewee.DateTimeField(default=datetime.datetime.now)
 
    class Meta:
        table_name = 'main_chatinvitelink'
 
 
# -=-=- Сообщение -=-=-
class Message(BaseModel):
    id = peewee.AutoField(primary_key=True)
    member_id = peewee.ForeignKeyField(ChatMember, backref='messages', on_delete='CASCADE')
    text = peewee.TextField(null=True)
    has_forbidden = peewee.BooleanField(default=False)
    date_create = peewee.DateTimeField(default=datetime.datetime.now)
 
    class Meta:
        table_name = 'main_message'
 
 
# -=-=- Вложение -=-=-
class AttachmentType(str):
    PHOTO = 'photo'
    VIDEO = 'video'
    AUDIO = 'audio'
    VOICE = 'voice'
    DOCUMENT = 'document'
    VIDEO_NOTE = 'video_note'
    STICKER = 'sticker'
 
ATTACHMENT_TYPES = [
    AttachmentType.PHOTO, AttachmentType.VIDEO, AttachmentType.AUDIO,
    AttachmentType.VOICE, AttachmentType.DOCUMENT,
    AttachmentType.VIDEO_NOTE, AttachmentType.STICKER,
]
 
 
class Attachment(BaseModel):
    id = peewee.AutoField(primary_key=True)
    message_id = peewee.ForeignKeyField(Message, backref='attachments', on_delete='CASCADE')
    id_file = peewee.CharField(max_length=512)
    attachment_type = peewee.CharField(max_length=50, default=AttachmentType.DOCUMENT)
    date_create = peewee.DateTimeField(default=datetime.datetime.now)
 
    class Meta:
        table_name = 'main_attachment'
 
 
# -=-=- Автоподключение -=-=-
class AutoConnect(BaseModel):
    id = peewee.AutoField(primary_key=True)
    profile_id = peewee.ForeignKeyField(Profile, backref='auto_connects', on_delete='CASCADE')
    date_create = peewee.DateTimeField(default=datetime.datetime.now)
 
    class Meta:
        table_name = 'main_autoconnect'
 
 
# -=-=- Фильтр ключевых слов (привязан к чату) -=-=-
class ChatFilter(BaseModel):
    id = peewee.AutoField(primary_key=True)
    chat_id = peewee.ForeignKeyField(Chat, backref='filters', on_delete='CASCADE')
    pattern = peewee.TextField()
    description = peewee.CharField(max_length=255, null=True)
    is_active = peewee.BooleanField(default=True)
    date_create = peewee.DateTimeField(default=datetime.datetime.now)
 
    class Meta:
        table_name = 'main_chatfilter'
 
    def __str__(self):
        short = self.pattern[:40] + '...' if len(self.pattern) > 40 else self.pattern
        return short
 
 
# -=-=- Глобальные фильтры -=-=-
class GlobalFilter(BaseModel):
    id = peewee.AutoField(primary_key=True)
    pattern = peewee.TextField()
    description = peewee.CharField(max_length=255, null=True)
    is_active = peewee.BooleanField(default=True)
    date_create = peewee.DateTimeField(default=datetime.datetime.now)
 
    class Meta:
        table_name = 'main_globalfilter'