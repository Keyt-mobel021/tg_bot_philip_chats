from django.contrib import admin
from .models import (
    UserTelegram, DataState,
    Profile, Company, Chat, ChatMember,
    Message, Attachment,
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

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'is_blocked', 'date_create',)

# ══════════════════════════════════════════════
#  Chat + inline участники
# ══════════════════════════════════════════════
class ChatMemberInline(admin.TabularInline):
    model = ChatMember
    extra = 0
    fields = ('user', 'profile', 'member_type', 'is_blocked', 'date_create')
    readonly_fields = ('date_create', 'connect_token')
    show_change_link = True


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'creator', 'is_visible', 'is_frozen', 'members_count', 'date_create')
    list_filter = ('is_visible', 'is_frozen')
    search_fields = ('title', 'description', 'creator__name')
    readonly_fields = ('date_create', 'members_count')
    list_editable = ('is_visible', 'is_frozen')
    ordering = ('-date_create',)
    inlines = [ChatMemberInline]
    fieldsets = (
        ('Основное', {
            'fields': ('title', 'description', 'creator'),
        }),
        ('Статус', {
            'fields': ('is_visible', 'is_frozen'),
        }),
        ('Служебное', {
            'fields': ('date_create',),
        }),
    )


# ══════════════════════════════════════════════
#  ChatMember
# ══════════════════════════════════════════════
@admin.register(ChatMember)
class ChatMemberAdmin(admin.ModelAdmin):
    list_display = ('id', 'chat', 'user', 'profile', 'member_type', 'is_blocked', 'date_create')
    list_filter = ('member_type', 'is_blocked')
    search_fields = (
        'user__full_name', 'user__id',
        'profile__name', 'chat__title',
    )
    readonly_fields = ('connect_token', 'date_create')
    list_editable = ('is_blocked',)
    ordering = ('-date_create',)


# ══════════════════════════════════════════════
#  Message + inline вложения
# ══════════════════════════════════════════════
class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    fields = ('attachment_type', 'file', 'date_create')
    readonly_fields = ('date_create',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'member', 'short_text', 'has_forbidden', 'date_create')
    list_filter = ('has_forbidden',)
    search_fields = ('text', 'member__profile__name', 'member__user__full_name')
    readonly_fields = ('date_create',)
    ordering = ('-date_create',)
    inlines = [AttachmentInline]

    @admin.display(description='Текст')
    def short_text(self, obj):
        if obj.text:
            return obj.text[:80] + '...' if len(obj.text) > 80 else obj.text
        return '📎 Вложение'


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