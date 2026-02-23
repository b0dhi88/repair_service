from django.views.generic import ListView, UpdateView, View, DetailView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

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


ACTIVE_STATUSES = [Request.Status.NEW, Request.Status.ASSIGNED, Request.Status.IN_PROGRESS]


class NewRequestListView(DispatcherRequiredMixin, ListView):
    model = Request
    template_name = 'dispatcher/new_requests.html'
    context_object_name = 'requests'
    paginate_by = 20

    def get_queryset(self):
        queryset = Request.objects.filter(
            status=Request.Status.NEW
        ).order_by('-created_at')
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset


class ActiveRequestListView(DispatcherRequiredMixin, ListView):
    model = Request
    template_name = 'dispatcher/active_requests.html'
    context_object_name = 'requests'
    paginate_by = 20

    def get_queryset(self):
        queryset = Request.objects.filter(
            status__in=ACTIVE_STATUSES
        ).order_by('-created_at')
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset


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


class CompletedRequestListView(DispatcherRequiredMixin, ListView):
    model = Request
    template_name = 'dispatcher/completed_requests.html'
    context_object_name = 'requests'
    paginate_by = 20

    def get_queryset(self):
        return Request.objects.filter(
            status=Request.Status.DONE
        ).order_by('-created_at')


class CanceledRequestListView(DispatcherRequiredMixin, ListView):
    model = Request
    template_name = 'dispatcher/canceled_requests.html'
    context_object_name = 'requests'
    paginate_by = 20

    def get_queryset(self):
        return Request.objects.filter(
            status=Request.Status.CANCELED
        ).order_by('-created_at')


class RequestAssignView(DispatcherRequiredMixin, UpdateView):
    model = Request
    template_name = 'dispatcher/request_assign.html'
    fields = ['assigned_to']
    success_url = reverse_lazy('dispatcher:new-requests')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['assigned_to'].queryset = User.objects.filter(role=User.Role.MASTER)
        return form

    def get_queryset(self):
        return Request.objects.filter(status__in=[Request.Status.NEW])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = self.request.META.get('HTTP_REFERER', '')
        return context

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
        
        form.instance.refresh_from_db()
        
        return super().form_valid(form)


class RequestReassignView(DispatcherRequiredMixin, UpdateView):
    model = Request
    template_name = 'dispatcher/request_reassign.html'
    fields = ['assigned_to']
    success_url = reverse_lazy('dispatcher:new-requests')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['assigned_to'].queryset = User.objects.filter(role=User.Role.MASTER)
        return form

    def get_queryset(self):
        return Request.objects.filter(
            status__in=[Request.Status.ASSIGNED, Request.Status.IN_PROGRESS]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = self.request.META.get('HTTP_REFERER', '')
        return context

    def form_valid(self, form):
        new_master = form.cleaned_data['assigned_to']
        old_master = form.instance.assigned_to
        service = RequestService()
        
        try:
            service.reassign_master(form.instance.pk, new_master, self.request.user)
            old_name = (old_master.get_full_name() or old_master.username) if old_master else 'None'
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
        
        form.instance.refresh_from_db()
        
        return super().form_valid(form)


class RequestCancelView(DispatcherRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        req = get_object_or_404(
            Request.objects.exclude(status__in=[Request.Status.DONE, Request.Status.CANCELED]),
            pk=pk
        )
        context = {'request': req}
        context['back_url'] = request.META.get('HTTP_REFERER', '')
        return render(request, 'dispatcher/request_cancel.html', context)

    def post(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        req = get_object_or_404(
            Request.objects.exclude(status__in=[Request.Status.DONE, Request.Status.CANCELED]),
            pk=pk
        )
        service = RequestService()
        
        try:
            service.cancel(req.pk, self.request.user)
            messages.success(self.request, 'Заявка отменена')
        except RequestPermissionError as e:
            messages.error(self.request, str(e))
            return redirect('dispatcher:request-cancel', pk=pk)
        except RequestValidationError as e:
            messages.error(self.request, str(e))
            return redirect('dispatcher:request-cancel', pk=pk)
        except ConcurrentModificationError:
            messages.error(
                self.request,
                'Заявка была изменена другим пользователем. Обновите страницу.'
            )
            return redirect('dispatcher:request-cancel', pk=pk)
        
        return redirect('dispatcher:active-requests')


class MasterListView(DispatcherRequiredMixin, ListView):
    model = User
    template_name = 'dispatcher/master_list.html'
    context_object_name = 'masters'
    
    def get_queryset(self):
        return User.objects.filter(role=User.Role.MASTER)


class RequestDetailView(DispatcherRequiredMixin, DetailView):
    model = Request
    template_name = 'dispatcher/request_detail.html'
    context_object_name = 'request'

    def get_queryset(self):
        return Request.objects.select_related('assigned_to')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = self.request.META.get('HTTP_REFERER', '')
        return context


class MasterRequestListView(DispatcherRequiredMixin, ListView):
    model = Request
    template_name = 'dispatcher/master_requests.html'
    context_object_name = 'requests'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        master = get_object_or_404(User, pk=self.kwargs['master_id'], role=User.Role.MASTER)
        context['master'] = master
        context['master_id'] = master.pk
        return context

    def get_queryset(self):
        master_id = self.kwargs['master_id']
        queryset = Request.objects.filter(
            assigned_to_id=master_id
        ).order_by('-created_at')

        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        return queryset
