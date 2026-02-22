from django.views.generic import ListView, UpdateView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.core.exceptions import PermissionDenied

from ..models import Request, User


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
        request = form.instance
        request.assigned_to = self.request.user
        request.status = Request.Status.ASSIGNED
        request.save(update_fields=['assigned_to', 'status', 'updated_at'])
        messages.success(self.request, 'Заявка взята в работу')
        return super().form_valid(form)


class RequestStartWorkView(MasterRequiredMixin, UpdateView):
    model = Request
    template_name = 'master/request_start_work.html'
    fields = []
    success_url = reverse_lazy('master:assigned-requests')

    def get_queryset(self):
        return Request.objects.filter(assigned_to=self.request.user)

    def form_valid(self, form):
        request = form.instance
        if not request.can_take_work(self.request.user):
            raise PermissionDenied('Вы не можете начать работу над этой заявкой')
        
        request.status = Request.Status.IN_PROGRESS
        request.save(update_fields=['status', 'updated_at'])
        messages.success(self.request, 'Работа над заявкой начата')
        return super().form_valid(form)


class RequestCompleteView(MasterRequiredMixin, UpdateView):
    model = Request
    template_name = 'master/request_complete.html'
    fields = []
    success_url = reverse_lazy('master:assigned-requests')

    def get_queryset(self):
        return Request.objects.filter(assigned_to=self.request.user)

    def form_valid(self, form):
        request = form.instance
        if not request.can_complete(self.request.user):
            raise PermissionDenied('Вы не можете завершить эту заявку')
        
        request.status = Request.Status.DONE
        request.save(update_fields=['status', 'updated_at'])
        messages.success(self.request, 'Заявка выполнена')
        return super().form_valid(form)
