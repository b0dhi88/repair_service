from django.urls import path
from ..views.master import (
    ActiveRequestListView,
    CompletedRequestListView,
    AvailableRequestListView,
    RequestTakeView,
    RequestStartWorkView,
    RequestCompleteView,
)

app_name = 'master'

urlpatterns = [
    path('requests/', ActiveRequestListView.as_view(), name='active-requests'),
    path('requests/completed/', CompletedRequestListView.as_view(), name='completed-requests'),
    path('requests/available/', AvailableRequestListView.as_view(), name='available-requests'),
    path('requests/<int:pk>/take/', RequestTakeView.as_view(), name='request-take'),
    path('requests/<int:pk>/start/', RequestStartWorkView.as_view(), name='request-start-work'),
    path('requests/<int:pk>/complete/', RequestCompleteView.as_view(), name='request-complete'),
]
