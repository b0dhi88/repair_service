from django.views.generic import ListView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import QuerySet


class RoleRequiredMixin(UserPassesTestMixin):
    """Base mixin for role-based access control."""
    role = None

    def test_func(self):
        if not self.request.user.is_authenticated:
            return False
        if self.role == 'client':
            return self.request.user.is_client
        elif self.role == 'dispatcher':
            return self.request.user.is_dispatcher
        elif self.role == 'master':
            return self.request.user.is_master
        return False


class ClientRequiredMixin(RoleRequiredMixin):
    role = 'client'


class DispatcherRequiredMixin(RoleRequiredMixin):
    role = 'dispatcher'


class MasterRequiredMixin(RoleRequiredMixin):
    role = 'master'


# Common status constants
ACTIVE_STATUSES = ['new', 'assigned', 'in_progress']


class BaseStatusFilterListView(ListView):
    """
    Base class for ListViews with status filtering and pagination.
    Subclasses should define:
    - status_filter: list of status values to filter by
    - user_field: string name of the field to filter by user (e.g., 'client' or 'assigned_to')
    """
    paginate_by = 10
    status_filter = None
    user_field = None
    model = None

    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()

        # Apply user filter if specified
        if self.user_field:
            queryset = queryset.filter(**{self.user_field: self.request.user})

        # Apply status filter if specified
        if self.status_filter is not None:
            queryset = queryset.filter(status__in=self.status_filter)

        # Apply status query param if provided
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by('-created_at')
