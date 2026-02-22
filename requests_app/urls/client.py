from django.urls import path
from ..views.client import RequestListView, RequestCreateView, RequestDetailView, RequestCancelView

app_name = 'client'

urlpatterns = [
    path('requests/', RequestListView.as_view(), name='request-list'),
    path('requests/create/', RequestCreateView.as_view(), name='request-create'),
    path('requests/<int:pk>/', RequestDetailView.as_view(), name='request-detail'),
    path('requests/<int:pk>/cancel/', RequestCancelView.as_view(), name='request-cancel'),
]
