from django.urls import path

from . import views

urlpatterns = [
    path("", views.DocumentListCreateView.as_view(), name="document-list-create"),
    path("<int:pk>/", views.DocumentDetailView.as_view(), name="document-detail"),
    path(
        "<int:document_id>/confirm/",
        views.DocumentConfirmView.as_view(),
        name="document-confirm",
    ),
    path(
        "<int:document_id>/reject/", views.DocumentRejectView.as_view(), name="document-reject"
    ),
]
