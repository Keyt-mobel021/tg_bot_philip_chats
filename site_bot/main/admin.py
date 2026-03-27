from django.contrib import admin
from django.utils.html import format_html
from .models import (
    UserTelegram, DataState,
    BotText,
    Profile, Company, Chat, ChatInviteLink, ChatMember,
    Message, MessageRead, Attachment,
    AutoConnect, ChatFilter, GlobalFilter,
)


# ══════════════════════════════════════════════
#  UserTelegram
# ══════════════════════════════════════════════
@admin.register(UserTelegram)
class UserTelegramAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'user_html', 'is_admin', 'is_block', 'appeal_time', 'date_create')
    list_filter = ('is_admin', 'is_block')
    search_fields = ('id', 'full_name', 'username')
    readonly_fields = ('date_create', 'appeal_time', 'user_html')
    list_editable = ('is_admin', 'is_block')
    ordering = ('-date_create',)


# ══════════════════════════════════════════════
#  DataState
# ══════════════════════════════════════════════
@admin.register(DataState)
class DataStateAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'state')
    search_fields = ('user__full_name', 'user__id', 'state')
    readonly_fields = ('user',)


# ══════════════════════════════════════════════
#  BotText
# ══════════════════════════════════════════════
@admin.register(BotText)
class BotTextAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'text_type', 'is_active', 'date_update', 'date_create')
    list_filter = ('text_type', 'is_active')
    search_fields = ('title', 'content')
    readonly_fields = ('date_create', 'date_update')
    list_editable = ('is_active',)
    ordering = ('-date_create',)
    fieldsets = (
        ('Основное', {
            'fields': ('text_type', 'title', 'is_active'),
        }),
        ('Текст (HTML)', {
            'fields': ('content',),
            'description': 'Поддерживается HTML-разметка Telegram: &lt;b&gt;, &lt;i&gt;, &lt;code&gt;, &lt;a href=...&gt;',
        }),
        ('Служебное', {
            'fields': ('date_create', 'date_update'),
        }),
    )


# ══════════════════════════════════════════════
#  Profile
# ══════════════════════════════════════════════
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'profile_type', 'position', 'user', 'is_blocked', 'connect_link_html', 'date_create')
    list_filter = ('profile_type', 'is_blocked')
    search_fields = ('name', 'position', 'user__full_name', 'user__id')
    readonly_fields = ('connect_token', 'connect_link_html', 'date_create')
    list_editable = ('is_blocked',)
    ordering = ('-date_create',)
    fieldsets = (
        ('Основное', {
            'fields': ('name', 'profile_type', 'position', 'is_blocked'),
        }),
        ('Telegram', {
            'fields': ('user',),
        }),
        ('Подключение', {
            'fields': ('connect_token', 'connect_link_html'),
        }),
        ('Служебное', {
            'fields': ('date_create',),
        }),
    )


# ══════════════════════════════════════════════
#  Company
# ══════════════════════════════════════════════
@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'is_blocked', 'members_count', 'date_create')
    list_filter = ('is_blocked',)
    search_fields = ('name',)
    readonly_fields = ('date_create', 'members_count')
    list_editable = ('is_blocked',)
    ordering = ('-date_create',)


# ══════════════════════════════════════════════
#  Chat + inline участники + inline ссылки
# ══════════════════════════════════════════════
class ChatMemberInline(admin.TabularInline):
    model = ChatMember
    extra = 0
    fields = ('user', 'profile', 'company', 'member_type', 'alias', 'is_blocked', 'date_create')
    readonly_fields = ('date_create', 'connect_token')
    show_change_link = True


class ChatInviteLinkInline(admin.TabularInline):
    model = ChatInviteLink
    extra = 0
    fields = ('invite_link_html', 'token', 'is_active', 'date_create')
    readonly_fields = ('invite_link_html', 'token', 'date_create')
    show_change_link = False


class ChatFilterInline(admin.TabularInline):
    model = ChatFilter
    extra = 0
    fields = ('pattern', 'description', 'is_active')
    show_change_link = True


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'creator', 'is_visible', 'is_frozen', 'members_count', 'date_create')
    list_filter = ('is_visible', 'is_frozen')
    search_fields = ('title', 'description', 'admin_description', 'creator__name')
    readonly_fields = ('date_create', 'members_count')
    list_editable = ('is_visible', 'is_frozen')
    ordering = ('-date_create',)
    inlines = [ChatMemberInline, ChatInviteLinkInline, ChatFilterInline]
    fieldsets = (
        ('Основное', {
            'fields': ('title', 'creator'),
        }),
        ('Описания', {
            'fields': ('description', 'admin_description'),
            'description': 'Приватное описание видят только администраторы и руководители',
        }),
        ('Статус', {
            'fields': ('is_visible', 'is_frozen'),
        }),
        ('Служебное', {
            'fields': ('date_create', 'members_count'),
        }),
    )


# ══════════════════════════════════════════════
#  ChatInviteLink
# ══════════════════════════════════════════════
@admin.register(ChatInviteLink)
class ChatInviteLinkAdmin(admin.ModelAdmin):
    list_display = ('id', 'chat', 'invite_link_html', 'is_active', 'date_create')
    list_filter = ('is_active', 'chat')
    search_fields = ('chat__title', 'token')
    readonly_fields = ('token', 'invite_link_html', 'date_create')
    list_editable = ('is_active',)
    ordering = ('-date_create',)


# ══════════════════════════════════════════════
#  ChatMember
# ══════════════════════════════════════════════
@admin.register(ChatMember)
class ChatMemberAdmin(admin.ModelAdmin):
    list_display = ('id', 'chat', 'display_name', 'member_type', 'company', 'alias', 'is_blocked', 'date_create')
    list_filter = ('member_type', 'is_blocked', 'chat')
    search_fields = (
        'user__full_name', 'user__id',
        'profile__name', 'chat__title',
        'alias', 'company__name',
    )
    readonly_fields = ('connect_token', 'date_create')
    list_editable = ('is_blocked',)
    ordering = ('-date_create',)
    fieldsets = (
        ('Основное', {
            'fields': ('chat', 'member_type', 'is_blocked'),
        }),
        ('Идентификация', {
            'fields': ('user', 'profile', 'company', 'alias'),
        }),
        ('Подключение', {
            'fields': ('connect_token',),
        }),
        ('Служебное', {
            'fields': ('date_create',),
        }),
    )


# ══════════════════════════════════════════════
#  Message + inline вложения
# ══════════════════════════════════════════════
class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    fields = ('attachment_type', 'id_file', 'date_create')
    readonly_fields = ('date_create',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'chat_title', 'member', 'short_text', 'has_forbidden', 'date_create')
    list_filter = ('has_forbidden', 'member__chat')
    search_fields = ('text', 'member__profile__name', 'member__user__full_name', 'member__chat__title')
    readonly_fields = ('date_create',)
    ordering = ('-date_create',)
    inlines = [AttachmentInline]

    @admin.display(description='Текст')
    def short_text(self, obj):
        if obj.text:
            return obj.text[:80] + '...' if len(obj.text) > 80 else obj.text
        return '📎 Вложение'

    @admin.display(description='Чат')
    def chat_title(self, obj):
        try:
            return obj.member.chat.title
        except Exception:
            return '—'


# ══════════════════════════════════════════════
#  MessageRead
# ══════════════════════════════════════════════
@admin.register(MessageRead)
class MessageReadAdmin(admin.ModelAdmin):
    list_display = ('id', 'member', 'chat_title', 'last_read_message_id', 'date_read')
    search_fields = ('member__profile__name', 'member__user__full_name', 'member__chat__title')
    readonly_fields = ('date_read',)
    ordering = ('-date_read',)

    @admin.display(description='Чат')
    def chat_title(self, obj):
        try:
            return obj.member.chat.title
        except Exception:
            return '—'


# ══════════════════════════════════════════════
#  Attachment
# ══════════════════════════════════════════════
@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'message', 'attachment_type', 'id_file', 'date_create')
    list_filter = ('attachment_type',)
    search_fields = ('id_file',)
    readonly_fields = ('date_create',)
    ordering = ('-date_create',)


# ══════════════════════════════════════════════
#  AutoConnect
# ══════════════════════════════════════════════
@admin.register(AutoConnect)
class AutoConnectAdmin(admin.ModelAdmin):
    list_display = ('id', 'profile', 'date_create')
    search_fields = ('profile__name',)
    readonly_fields = ('date_create',)
    ordering = ('-date_create',)


# ══════════════════════════════════════════════
#  ChatFilter
# ══════════════════════════════════════════════
@admin.register(ChatFilter)
class ChatFilterAdmin(admin.ModelAdmin):
    list_display = ('id', 'chat', 'short_pattern', 'description', 'is_active', 'date_create')
    list_filter = ('is_active', 'chat')
    search_fields = ('pattern', 'description', 'chat__title')
    readonly_fields = ('date_create',)
    list_editable = ('is_active',)
    ordering = ('-date_create',)

    @admin.display(description='Паттерн')
    def short_pattern(self, obj):
        return obj.pattern[:60] + '...' if len(obj.pattern) > 60 else obj.pattern


# ══════════════════════════════════════════════
#  GlobalFilter
# ══════════════════════════════════════════════
@admin.register(GlobalFilter)
class GlobalFilterAdmin(admin.ModelAdmin):
    list_display = ('id', 'short_pattern', 'description', 'is_active', 'date_create')
    list_filter = ('is_active',)
    search_fields = ('pattern', 'description')
    readonly_fields = ('date_create',)
    list_editable = ('is_active',)
    ordering = ('-date_create',)

    @admin.display(description='Паттерн')
    def short_pattern(self, obj):
        return obj.pattern[:60] + '...' if len(obj.pattern) > 60 else obj.pattern