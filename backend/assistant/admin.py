from django.contrib import admin

from .models import Conversation, Message, PendingAction


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "company", "user", "started_at", "last_message_at"]
    inlines = [MessageInline]


@admin.register(PendingAction)
class PendingActionAdmin(admin.ModelAdmin):
    list_display = ["id", "company", "user", "intent_name", "status", "created_at", "expires_at"]
    list_filter = ["status", "intent_name"]
