import peewee
import datetime
from fuzzywuzzy import fuzz


connector = peewee.SqliteDatabase('filter_bot.db')


# -=-=- Модель Чата/Группы в Telegram -=-=-
class ChatGroup(peewee.Model):
    # Id Telegram (может быть отрицательным для групп)
    id = peewee.BigIntegerField(unique=True, primary_key=True)
    # Название чата
    title = peewee.CharField(max_length=255, null=True)
    # Username чата
    username = peewee.CharField(max_length=255, null=True)
    # Это группа?
    is_group = peewee.BooleanField(default=False)
    # Активен ли мониторинг
    is_active = peewee.BooleanField(default=True)
    # Порог нечеткого совпадения (0-100), по умолчанию 80
    fuzzy_threshold = peewee.IntegerField(default=80)
    # Дата создания
    date_create = peewee.DateTimeField(default=datetime.datetime.now)

    class Meta:
        database = connector
        table_name = 'chat_group'

    def __str__(self):
        return self.title or str(self.id)


# -=-=- Модель Фильтра ключевых слов -=-=-
class ChatFilter(peewee.Model):
    id = peewee.AutoField(primary_key=True)
    # Привязка к чату
    chat_id = peewee.ForeignKeyField(ChatGroup, related_name='filters', on_delete='CASCADE')
    # Regex выражение
    pattern = peewee.TextField()
    # Описание фильтра (необязательно)
    description = peewee.CharField(max_length=255, null=True)
    # Активен ли фильтр
    is_active = peewee.BooleanField(default=True)
    # Дата создания
    date_create = peewee.DateTimeField(default=datetime.datetime.now)

    class Meta:
        database = connector
        table_name = 'chat_filter'

    def __str__(self):
        short = self.pattern[:40] + '...' if len(self.pattern) > 40 else self.pattern
        return short


# -=-=- Модель Администратора бота -=-=-
class AdminUser(peewee.Model):
    id = peewee.BigIntegerField(unique=True, primary_key=True)
    full_name = peewee.CharField(max_length=255, null=True)
    username = peewee.CharField(max_length=255, null=True)
    date_create = peewee.DateTimeField(default=datetime.datetime.now)

    class Meta:
        database = connector
        table_name = 'admin_user'


# -=-=- Модель заблокированных пользователей -=-=-
class BlockedUser(peewee.Model):
    id = peewee.AutoField(primary_key=True)
    # Telegram ID пользователя
    user_id = peewee.BigIntegerField()
    # Имя пользователя
    full_name = peewee.CharField(max_length=255, null=True)
    # Username
    username = peewee.CharField(max_length=255, null=True)
    # Привязка к группе
    chat_id = peewee.ForeignKeyField(ChatGroup, related_name='blocked_users', on_delete='CASCADE')
    # Сообщение из-за которого заблокировали
    trigger_message = peewee.TextField(null=True)
    # Дата блокировки
    date_create = peewee.DateTimeField(default=datetime.datetime.now)

    class Meta:
        database = connector
        table_name = 'blocked_user'

def init_db():
    with connector:
        connector.create_tables([ChatGroup, ChatFilter, AdminUser, BlockedUser], safe=True)
