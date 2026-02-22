from django.urls import path
from django.views.generic import RedirectView
from ..views.client import (
    ClientRequestDashboardView,
    ActiveRequestListView,
    CompletedRequestListView,
    CanceledRequestListView,
    RequestCreateView,
    RequestDetailView,
    RequestCancelView,
)

app_name = 'client'

urlpatterns = [
    path('requests/dashboard/', ClientRequestDashboardView.as_view(), name='request-dashboard'),
    path('requests/', ClientRequestDashboardView.as_view(), name='request-list'),
    path('requests/active/', ActiveRequestListView.as_view(), name='request-active'),
    path('requests/completed/', CompletedRequestListView.as_view(), name='request-completed'),
    path('requests/canceled/', CanceledRequestListView.as_view(), name='request-canceled'),
    path('requests/create/', RequestCreateView.as_view(), name='request-create'),
    path('requests/<int:pk>/', RequestDetailView.as_view(), name='request-detail'),
    path('requests/<int:pk>/cancel/', RequestCancelView.as_view(), name='request-cancel'),
]
