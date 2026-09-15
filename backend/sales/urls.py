from django.urls import path

from . import views

urlpatterns = [
    path("", views.SaleListCreateView.as_view(), name="sale-list-create"),
    path("summary/", views.SaleSummaryView.as_view(), name="sale-summary"),
]
