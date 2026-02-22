from django.views.generic import ListView, UpdateView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.core.exceptions import PermissionDenied

from ..models import Request, User
from ..services import (
    RequestService,
    RequestPermissionError,
    RequestValidationError,
    ConcurrentModificationError,
)


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
        master = form.cleaned_data['assigned_to']
        service = RequestService()
        
        try:
            service.assign_master(form.instance.pk, master, self.request.user)
            messages.success(
                self.request,
                f'Заявка назначена мастеру {master.get_full_name() or master.username}'
            )
        except RequestPermissionError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        except RequestValidationError as e:
            form.add_error(e.field or '__all__', str(e))
            return self.form_invalid(form)
        except ConcurrentModificationError:
            messages.error(
                self.request,
                'Заявка была изменена другим пользователем. Обновите страницу.'
            )
            return self.form_invalid(form)
        
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
        new_master = form.cleaned_data['assigned_to']
        old_master = form.instance.assigned_to
        service = RequestService()
        
        try:
            service.reassign_master(form.instance.pk, new_master, self.request.user)
            old_name = old_master.get_full_name() or old_master.username if old_master else 'None'
            new_name = new_master.get_full_name() or new_master.username
            messages.success(
                self.request,
                f'Заявка переназначена с {old_name} на {new_name}'
            )
        except RequestPermissionError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        except RequestValidationError as e:
            form.add_error(e.field or '__all__', str(e))
            return self.form_invalid(form)
        except ConcurrentModificationError:
            messages.error(
                self.request,
                'Заявка была изменена другим пользователем. Обновите страницу.'
            )
            return self.form_invalid(form)
        
        return super().form_valid(form)


class RequestCancelView(DispatcherRequiredMixin, UpdateView):
    model = Request
    template_name = 'dispatcher/request_cancel.html'
    fields = []
    success_url = reverse_lazy('dispatcher:all-requests')

    def get_queryset(self):
        return Request.objects.exclude(status__in=[Request.Status.DONE, Request.Status.CANCELED])

    def form_valid(self, form):
        service = RequestService()
        
        try:
            service.cancel(form.instance.pk, self.request.user)
            messages.success(self.request, 'Заявка отменена')
        except RequestPermissionError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        except RequestValidationError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        except ConcurrentModificationError:
            messages.error(
                self.request,
                'Заявка была изменена другим пользователем. Обновите страницу.'
            )
            return self.form_invalid(form)
        
        return super().form_valid(form)


class MasterListView(DispatcherRequiredMixin, ListView):
    model = User
    template_name = 'dispatcher/master_list.html'
    context_object_name = 'masters'
    
    def get_queryset(self):
        return User.objects.filter(role=User.Role.MASTER)
