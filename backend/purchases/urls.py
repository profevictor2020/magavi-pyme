from django.urls import path

from . import views

urlpatterns = [
    path("", views.PurchaseListCreateView.as_view(), name="purchase-list-create"),
    path("summary/", views.PurchaseSummaryView.as_view(), name="purchase-summary"),
]
