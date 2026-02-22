from django.views.generic import ListView, UpdateView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.core.exceptions import PermissionDenied

from ..models import Request, User


class DispatcherRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.is_dispatcher


class AllRequestListView(DispatcherRequiredMixin, ListView):
    model = Request
    template_name = 'dispatcher/all_requests.html'
    context_object_name = 'requests'
    paginate_by = 20

    def get_queryset(self):
        queryset = Request.objects.all().order_by('-created_at')
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset


class RequestAssignView(DispatcherRequiredMixin, UpdateView):
    model = Request
    template_name = 'dispatcher/request_assign.html'
    fields = ['assigned_to']
    success_url = reverse_lazy('dispatcher:all-requests')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['assigned_to'].queryset = User.objects.filter(role=User.Role.MASTER)
        return form

    def get_queryset(self):
        return Request.objects.filter(status__in=[Request.Status.NEW])

    def form_valid(self, form):
        request = form.instance
        if request.status != Request.Status.NEW:
            raise PermissionDenied('Можно назначать только новые заявки')
        
        request.status = Request.Status.ASSIGNED
        request.save(update_fields=['assigned_to', 'status', 'updated_at'])
        messages.success(self.request, f'Заявка назначена мастеру {request.assigned_to}')
        return super().form_valid(form)


class RequestReassignView(DispatcherRequiredMixin, UpdateView):
    model = Request
    template_name = 'dispatcher/request_reassign.html'
    fields = ['assigned_to']
    success_url = reverse_lazy('dispatcher:all-requests')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['assigned_to'].queryset = User.objects.filter(role=User.Role.MASTER)
        return form

    def get_queryset(self):
        return Request.objects.filter(
            status__in=[Request.Status.ASSIGNED, Request.Status.IN_PROGRESS]
        )

    def form_valid(self, form):
        old_master = form.instance.assigned_to
        form.instance.status = Request.Status.ASSIGNED
        form.instance.save(update_fields=['assigned_to', 'status', 'updated_at'])
        messages.success(self.request, f'Заявка переназначена с {old_master} на {form.instance.assigned_to}')
        return super().form_valid(form)


class RequestCancelView(DispatcherRequiredMixin, UpdateView):
    model = Request
    template_name = 'dispatcher/request_cancel.html'
    fields = []
    success_url = reverse_lazy('dispatcher:all-requests')

    def get_queryset(self):
        return Request.objects.exclude(status__in=[Request.Status.DONE, Request.Status.CANCELED])

    def form_valid(self, form):
        form.instance.status = Request.Status.CANCELED
        form.instance.save(update_fields=['status', 'updated_at'])
        messages.success(self.request, 'Заявка отменена')
        return super().form_valid(form)


class MasterListView(DispatcherRequiredMixin, ListView):
    model = User
    template_name = 'dispatcher/master_list.html'
    context_object_name = 'masters'
    
    def get_queryset(self):
        return User.objects.filter(role=User.Role.MASTER)
