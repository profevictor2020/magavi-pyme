from django.urls import path

from . import views

urlpatterns = [
    path(
        "conversations/",
        views.ConversationListCreateView.as_view(),
        name="conversation-list-create",
    ),
    path(
        "conversations/<int:conversation_id>/messages/",
        views.MessageListCreateView.as_view(),
        name="message-list-create",
    ),
    path("chat/", views.ChatView.as_view(), name="assistant-chat"),
    path("intents/", views.IntentProposeView.as_view(), name="intent-propose"),
    path(
        "intents/<int:pending_action_id>/confirm/",
        views.IntentConfirmView.as_view(),
        name="intent-confirm",
    ),
    path(
        "intents/<int:pending_action_id>/cancel/",
        views.IntentCancelView.as_view(),
        name="intent-cancel",
    ),
]
