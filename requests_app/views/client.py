from django.views.generic import ListView, CreateView, DetailView, UpdateView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.core.exceptions import PermissionDenied

from ..models import Request, User


class ClientRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_client


class RequestListView(ClientRequiredMixin, ListView):
    model = Request
    template_name = 'client/request_list.html'
    context_object_name = 'requests'
    paginate_by = 10

    def get_queryset(self):
        return Request.objects.filter(client=self.request.user).order_by('-created_at')


class RequestCreateView(ClientRequiredMixin, CreateView):
    model = Request
    template_name = 'client/request_form.html'
    fields = ['client_name', 'phone', 'address', 'problem_text']
    success_url = reverse_lazy('client:request-list')

    def get_initial(self):
        initial = super().get_initial()
        user = self.request.user
        initial['client_name'] = user.get_full_name() or user.username
        initial['phone'] = user.phone
        return initial

    def form_valid(self, form):
        form.instance.client = self.request.user
        messages.success(self.request, 'Заявка успешно создана')
        return super().form_valid(form)


class RequestDetailView(ClientRequiredMixin, DetailView):
    model = Request
    template_name = 'client/request_detail.html'
    context_object_name = 'request'

    def get_queryset(self):
        return Request.objects.filter(client=self.request.user)


class RequestCancelView(ClientRequiredMixin, UpdateView):
    model = Request
    template_name = 'client/request_cancel.html'
    fields = []
    success_url = reverse_lazy('client:request-list')

    def get_queryset(self):
        return Request.objects.filter(client=self.request.user)

    def form_valid(self, form):
        request = form.instance
        if not request.can_cancel(self.request.user):
            raise PermissionDenied('Вы не можете отменить эту заявку')
        
        request.status = Request.Status.CANCELED
        request.save(update_fields=['status', 'updated_at'])
        messages.success(self.request, 'Заявка отменена')
        return super().form_valid(form)
