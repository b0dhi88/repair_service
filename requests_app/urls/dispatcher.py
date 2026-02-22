from django.urls import path
from ..views.dispatcher import AllRequestListView, RequestAssignView, RequestReassignView, RequestCancelView, MasterListView

app_name = 'dispatcher'

urlpatterns = [
    path('requests/', AllRequestListView.as_view(), name='all-requests'),
    path('requests/<int:pk>/assign/', RequestAssignView.as_view(), name='request-assign'),
    path('requests/<int:pk>/reassign/', RequestReassignView.as_view(), name='request-reassign'),
    path('requests/<int:pk>/cancel/', RequestCancelView.as_view(), name='request-cancel'),
    path('masters/', MasterListView.as_view(), name='master-list'),
]
