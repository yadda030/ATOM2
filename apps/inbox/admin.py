from django.contrib import admin
from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    fields = ('sender', 'body', 'is_read', 'created_at')
    readonly_fields = ('sender', 'body', 'is_read', 'created_at')
    extra = 0
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'participant_names', 'message_count', 'updated_at')
    readonly_fields = ('participants', 'created_at', 'updated_at')
    inlines = [MessageInline]

    def participant_names(self, obj):
        return ', '.join(u.username for u in obj.participants.all())
    participant_names.short_description = 'Participants'

    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Messages'

    def has_add_permission(self, request):
        return False


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'conversation', 'short_body', 'is_read', 'created_at')
    list_filter = ('is_read',)
    search_fields = ('sender__username', 'body')
    readonly_fields = ('sender', 'conversation', 'body', 'is_read', 'created_at')

    def short_body(self, obj):
        return obj.body[:60] + '...' if len(obj.body) > 60 else obj.body
    short_body.short_description = 'Message'

    def has_add_permission(self, request):
        return False
