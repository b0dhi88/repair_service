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


class ActiveRequestListView(MasterRequiredMixin, ListView):
    model = Request
    template_name = 'master/active_requests.html'
    context_object_name = 'requests'
    paginate_by = 10

    def get_queryset(self):
        in_progress = Request.objects.filter(
            assigned_to=self.request.user,
            status=Request.Status.IN_PROGRESS
        ).order_by('-created_at')
        
        assigned = Request.objects.filter(
            assigned_to=self.request.user,
            status=Request.Status.ASSIGNED
        ).order_by('-created_at')
        
        return list(in_progress) + list(assigned)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stats'] = self.get_stats()
        
        in_progress = [r for r in context['requests'] if str(r.status) == 'in_progress']
        assigned = [r for r in context['requests'] if str(r.status) == 'assigned']
        
        context['in_progress_requests'] = in_progress
        context['assigned_requests'] = assigned
        
        return context

    def get_stats(self):
        in_progress_count = Request.objects.filter(
            assigned_to=self.request.user,
            status=Request.Status.IN_PROGRESS
        ).count()
        
        assigned_count = Request.objects.filter(
            assigned_to=self.request.user,
            status=Request.Status.ASSIGNED
        ).count()
        
        return {
            'in_progress': in_progress_count,
            'assigned': assigned_count,
            'active': in_progress_count + assigned_count,
            'completed': Request.objects.filter(
                assigned_to=self.request.user,
                status=Request.Status.DONE
            ).count(),
        }


class CompletedRequestListView(MasterRequiredMixin, ListView):
    model = Request
    template_name = 'master/completed_requests.html'
    context_object_name = 'requests'
    paginate_by = 10

    def get_queryset(self):
        return Request.objects.filter(
            assigned_to=self.request.user,
            status=Request.Status.DONE
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stats'] = self.get_stats()
        return context

    def get_stats(self):
        return {
            'active': Request.objects.filter(
                assigned_to=self.request.user,
                status__in=[Request.Status.ASSIGNED, Request.Status.IN_PROGRESS]
            ).count(),
            'completed': Request.objects.filter(
                assigned_to=self.request.user,
                status=Request.Status.DONE
            ).count(),
        }


class RequestStartWorkView(MasterRequiredMixin, UpdateView):
    model = Request
    template_name = 'master/request_start_work.html'
    fields = []
    success_url = reverse_lazy('master:active-requests')

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
    success_url = reverse_lazy('master:active-requests')

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
