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


class MasterRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_master


class AvailableRequestListView(MasterRequiredMixin, ListView):
    model = Request
    template_name = 'master/available_requests.html'
    context_object_name = 'requests'
    paginate_by = 10

    def get_queryset(self):
        return Request.objects.filter(
            status__in=[Request.Status.NEW, Request.Status.ASSIGNED]
        ).exclude(assigned_to=self.request.user).order_by('-created_at')


class AssignedRequestListView(MasterRequiredMixin, ListView):
    model = Request
    template_name = 'master/assigned_requests.html'
    context_object_name = 'requests'
    paginate_by = 10

    def get_queryset(self):
        return Request.objects.filter(
            assigned_to=self.request.user
        ).order_by('-created_at')


class RequestTakeView(MasterRequiredMixin, UpdateView):
    model = Request
    template_name = 'master/request_take.html'
    fields = []
    success_url = reverse_lazy('master:assigned-requests')

    def get_queryset(self):
        return Request.objects.filter(status=Request.Status.NEW)

    def form_valid(self, form):
        service = RequestService()
        
        try:
            service.take_work(form.instance.pk, self.request.user)
            messages.success(self.request, 'Заявка взята в работу')
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


class RequestStartWorkView(MasterRequiredMixin, UpdateView):
    model = Request
    template_name = 'master/request_start_work.html'
    fields = []
    success_url = reverse_lazy('master:assigned-requests')

    def get_queryset(self):
        return Request.objects.filter(assigned_to=self.request.user)

    def form_valid(self, form):
        service = RequestService()
        
        try:
            service.start_work(form.instance.pk, self.request.user)
            messages.success(self.request, 'Работа над заявкой начата')
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


class RequestCompleteView(MasterRequiredMixin, UpdateView):
    model = Request
    template_name = 'master/request_complete.html'
    fields = []
    success_url = reverse_lazy('master:assigned-requests')

    def get_queryset(self):
        return Request.objects.filter(assigned_to=self.request.user)

    def form_valid(self, form):
        service = RequestService()
        
        try:
            service.complete(form.instance.pk, self.request.user)
            messages.success(self.request, 'Заявка выполнена')
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
