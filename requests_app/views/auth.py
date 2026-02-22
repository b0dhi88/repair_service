from django.contrib.auth.views import LoginView
from django.contrib.auth import logout as auth_logout
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views import View


class RoleBasedLoginView(LoginView):
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
