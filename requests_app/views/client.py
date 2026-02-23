from django.views.generic import ListView, CreateView, DetailView, View
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django import forms
import logging

logger = logging.getLogger(__name__)

from ..models import Request, User
from ..services import (
    RequestService,
    RequestPermissionError,
    RequestValidationError,
)


class RequestForm(forms.ModelForm):
    class Meta:
        model = Request
        fields = ['address', 'problem_text']
        widgets = {
            'address': forms.TextInput(),
            'problem_text': forms.Textarea(attrs={'rows': 3}),
        }


class ClientRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_client


ACTIVE_STATUSES = [Request.Status.NEW, Request.Status.ASSIGNED, Request.Status.IN_PROGRESS]


class ActiveRequestListView(ClientRequiredMixin, ListView):
    model = Request
    template_name = 'client/request_list_active.html'
    context_object_name = 'requests'
    paginate_by = 10

    def get_queryset(self):
        return Request.objects.filter(
            client=self.request.user,
            status__in=ACTIVE_STATUSES
        ).select_related('assigned_to').order_by('-created_at')


class CompletedRequestListView(ClientRequiredMixin, ListView):
    model = Request
    template_name = 'client/request_list_completed.html'
    context_object_name = 'requests'
    paginate_by = 10

    def get_queryset(self):
        return Request.objects.filter(
            client=self.request.user,
            status=Request.Status.DONE
        ).select_related('assigned_to').order_by('-created_at')


class CanceledRequestListView(ClientRequiredMixin, ListView):
    model = Request
    template_name = 'client/request_list_canceled.html'
    context_object_name = 'requests'
    paginate_by = 10

    def get_queryset(self):
        return Request.objects.filter(
            client=self.request.user,
            status=Request.Status.CANCELED
        ).order_by('-created_at')


class RequestCreateView(ClientRequiredMixin, CreateView):
    form_class = RequestForm
    template_name = 'client/request_form.html'
    success_url = reverse_lazy('client:request-list')

    def form_valid(self, form):
        service = RequestService()
        try:
            self.object = service.create_request(self.request.user, form.cleaned_data)
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
        return Request.objects.filter(client=self.request.user).select_related('assigned_to')


class RequestCancelView(ClientRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        req = get_object_or_404(
            Request.objects.filter(client=request.user),
            pk=pk
        )
        return render(request, 'client/request_cancel.html', {'request': req})

    def post(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        req = get_object_or_404(
            Request.objects.filter(client=request.user),
            pk=pk
        )
        service = RequestService()
        try:
            service.cancel(req.pk, self.request.user)
            messages.success(self.request, 'Заявка отменена')
        except RequestPermissionError as e:
            messages.error(self.request, str(e))
            return redirect('client:request-cancel', pk=pk)
        except RequestValidationError as e:
            messages.error(self.request, str(e))
            return redirect('client:request-cancel', pk=pk)
        return redirect('client:request-list')


class ClientRequestDashboardView(ClientRequiredMixin, View):
    template_name = 'client/request_dashboard.html'

    def get(self, request):
        active_requests = Request.objects.filter(
            client=request.user,
            status__in=ACTIVE_STATUSES
        ).select_related('assigned_to').order_by('-created_at')[:30]

        active_count = Request.objects.filter(
            client=request.user,
            status__in=ACTIVE_STATUSES
        ).count()

        completed_requests = Request.objects.filter(
            client=request.user,
            status=Request.Status.DONE
        ).select_related('assigned_to').order_by('-created_at')[:3]

        completed_count = Request.objects.filter(
            client=request.user,
            status=Request.Status.DONE
        ).count()

        canceled_requests = Request.objects.filter(
            client=request.user,
            status=Request.Status.CANCELED
        ).select_related('assigned_to').order_by('-created_at')[:3]

        canceled_count = Request.objects.filter(
            client=request.user,
            status=Request.Status.CANCELED
        ).count()

        return render(request, self.template_name, {
            'active_requests': active_requests,
            'active_count': active_count,
            'completed_requests': completed_requests,
            'completed_count': completed_count,
            'canceled_requests': canceled_requests,
            'canceled_count': canceled_count,
        })
