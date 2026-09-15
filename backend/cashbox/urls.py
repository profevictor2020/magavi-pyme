from django.urls import path

from . import views

urlpatterns = [
    path("summary/", views.CashboxSummaryView.as_view(), name="cashbox-summary"),
]
