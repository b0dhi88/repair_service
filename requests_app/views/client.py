from django.views.generic import ListView, CreateView, DetailView, UpdateView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied

from ..models import Request, User
from ..services import (
    RequestService,
    RequestPermissionError,
    RequestValidationError,
)


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
        service = RequestService()
        try:
            service.create_request(self.request.user, form.cleaned_data)
            messages.success(self.request, 'Заявка успешно создана')
        except RequestPermissionError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        except RequestValidationError as e:
            form.add_error(e.field or '__all__', str(e))
            return self.form_invalid(form)
        return redirect(self.get_success_url())


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
        return redirect(self.get_success_url())
