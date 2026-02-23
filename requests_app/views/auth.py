from django.contrib.auth.views import LoginView
from django.contrib.auth import logout as auth_logout
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views import View
from django.views.generic import RedirectView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
import random

from requests_app.models import User, Request


class GetFreeMasterView(View):
    """Получение ID любого мастера без активных заявок в работе"""
    
    def get(self, request):
        busy_master_ids = Request.objects.filter(
            status=Request.Status.IN_PROGRESS,
            assigned_to__isnull=False
        ).values_list('assigned_to_id', flat=True).distinct()
        
        free_master = User.objects.filter(
            role=User.Role.MASTER
        ).exclude(
            id__in=busy_master_ids
        ).first()
        
        if free_master:
            return JsonResponse({'master_id': free_master.id, 'master_username': free_master.username})
        return JsonResponse({'error': 'Нет свободных мастеров'}, status=404)


class GetRandomMasterView(View):
    """Получение ID случайного мастера (может быть занят)"""
    
    def get(self, request):
        master_ids = list(User.objects.filter(
            role=User.Role.MASTER
        ).values_list('id', flat=True))
        
        if not master_ids:
            return JsonResponse({'error': 'Нет мастеров'}, status=404)
        
        random_master_id = random.choice(master_ids)
        master = User.objects.get(id=random_master_id)
        
        return JsonResponse({'master_id': master.id, 'master_username': master.username})


class GetMasterUsernameView(View):
    """Получение username мастера по его pid (user_id)"""
    
    def get(self, request, pid):
        try:
            master = User.objects.get(id=pid, role=User.Role.MASTER)
            return JsonResponse({'username': master.username})
        except User.DoesNotExist:
            return JsonResponse({'error': 'Мастер не найден'}, status=404)


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


class TestMessagesView(View):
    """Тестовое представление для проверки очереди сообщений"""
    
    def get(self, request):
        # Создаем 8 тестовых сообщений
        test_messages = [
            (messages.INFO, 'Это тестовое информационное сообщение №1'),
            (messages.SUCCESS, 'Успешное действие выполнено! №2'),
            (messages.WARNING, 'Внимание! Предупреждение №3'),
            (messages.ERROR, 'Произошла ошибка №4'),
            (messages.INFO, 'Информационное сообщение №5'),
            (messages.SUCCESS, 'Данные сохранены успешно №6'),
            (messages.WARNING, 'Срок действия истекает скоро №7'),
            (messages.ERROR, 'Ошибка валидации данных №8'),
        ]
        
        for level, msg in test_messages:
            messages.add_message(request, level, msg)
        
        # Перенаправляем на главную страницу для авторизованных
        # или на страницу входа для неавторизованных
        if request.user.is_authenticated:
            return redirect('/')
        else:
            return redirect('/login/')


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
