from django.urls import path
from ..views.master import AssignedRequestListView, AvailableRequestListView, RequestTakeView, RequestStartWorkView, RequestCompleteView

app_name = 'master'

urlpatterns = [
    path('requests/', AssignedRequestListView.as_view(), name='assigned-requests'),
    path('requests/available/', AvailableRequestListView.as_view(), name='available-requests'),
    path('requests/<int:pk>/take/', RequestTakeView.as_view(), name='request-take'),
    path('requests/<int:pk>/start/', RequestStartWorkView.as_view(), name='request-start-work'),
    path('requests/<int:pk>/complete/', RequestCompleteView.as_view(), name='request-complete'),
]
