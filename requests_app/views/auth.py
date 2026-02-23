from django.contrib.auth.views import LoginView
from django.contrib.auth import logout as auth_logout
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views import View
from django.views.generic import RedirectView
from django.contrib.auth.mixins import LoginRequiredMixin


class RootView(LoginRequiredMixin, RedirectView):
    def get_redirect_url(self):
        user = self.request.user
        if user.is_dispatcher:
            return '/dispatcher/requests/'
        elif user.is_master:
            return '/master/requests/'
        elif user.is_client:
            return '/client/requests/'
        return '/'


class RoleBasedLoginView(LoginView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['test_users'] = [
            {'username': 'client1', 'password': 'client123'},
            {'username': 'client2', 'password': 'client123'},
            {'username': 'client3', 'password': 'client123'},
            {'username': 'dispatcher1', 'password': 'dispatcher123'},
            {'username': 'master1', 'password': 'master123'},
            {'username': 'master2', 'password': 'master123'},
        ]
        return context

    def get_success_url(self):
        user = self.request.user
        if user.is_dispatcher:
            return '/dispatcher/requests/'
        elif user.is_master:
            return '/master/requests/'
        elif user.is_client:
            return '/client/requests/'
        return '/'

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'redirect': self.get_success_url()})
        return response

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {field: list(errors) for field, errors in form.errors.items()}
            return JsonResponse({'errors': errors}, status=400)
        return super().form_invalid(form)


class RoleBasedLogoutView(View):
    def get_success_url(self):
        return '/login/'

    def get(self, request, *args, **kwargs):
        auth_logout(request)
        return redirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        auth_logout(request)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'redirect': self.get_success_url()})
        return redirect(self.get_success_url())
