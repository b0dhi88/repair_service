from django.urls import path
from ..views.master import (
    ActiveRequestListView,
    CompletedRequestListView,
    RequestStartWorkView,
    RequestCompleteView,
)

app_name = 'master'

urlpatterns = [
    path('requests/', ActiveRequestListView.as_view(), name='active-requests'),
    path('requests/completed/', CompletedRequestListView.as_view(), name='completed-requests'),
    path('requests/<int:pk>/start/', RequestStartWorkView.as_view(), name='request-start-work'),
    path('requests/<int:pk>/complete/', RequestCompleteView.as_view(), name='request-complete'),
]
