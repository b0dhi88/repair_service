from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError

class User(AbstractUser):
    class Role(models.TextChoices):
        CLIENT = 'client', 'Клиент'
        DISPATCHER = 'dispatcher', 'Диспетчер'
        MASTER = 'master', 'Мастер'
    
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CLIENT,
        db_index=True,
        verbose_name='Роль'
    )
    
    # Телефон обязателен и уникален для всех пользователей
    phone = models.CharField(
        max_length=20,
        unique=True,  # Уникальность телефона
        verbose_name='Телефон'
    )
    
    # Дополнительные поля
    is_verified = models.BooleanField(default=False, verbose_name='Подтвержден')
    
    # Переопределяем поле email, делаем его необязательным
    email = models.EmailField(blank=True, verbose_name='Email')
    
    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['role']),
        ]
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    def clean(self):
        """Валидация модели"""
        super().clean()
        if not self.phone:
            raise ValidationError({'phone': 'Телефон обязателен для заполнения'})
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    @property
    def is_client(self):
        return self.role == self.Role.CLIENT
    
    @property
    def is_dispatcher(self):
        return self.role == self.Role.DISPATCHER
    
    @property
    def is_master(self):
        return self.role == self.Role.MASTER


class Request(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', 'Новая'
        ASSIGNED = 'assigned', 'Назначена'
        IN_PROGRESS = 'in_progress', 'В работе'
        DONE = 'done', 'Выполнена'
        CANCELED = 'canceled', 'Отменена'
    
    # Связь с клиентом (обязательно)
    client = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='client_requests',
        limit_choices_to={'role': User.Role.CLIENT},
        verbose_name='Клиент'
    )
    
    # Данные клиента (могут дублироваться на момент создания)
    client_name = models.CharField(
        max_length=255,
        verbose_name='Имя клиента'
    )
    phone = models.CharField(
        max_length=20,
        verbose_name='Телефон'
    )
    address = models.TextField(
        verbose_name='Адрес'
    )
    problem_text = models.TextField(
        verbose_name='Описание проблемы'
    )
    
    # Статус и назначение
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
        verbose_name='Статус'
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': User.Role.MASTER},
        related_name='assigned_requests',
        verbose_name='Назначена мастеру'
    )
    
    # Временные метки
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Создана')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлена')
    
    # Поле для оптимистичной блокировки (для решения проблемы гонок)
    version = models.IntegerField(default=1, verbose_name='Версия')
    
    class Meta:
        verbose_name = 'Заявка'
        verbose_name_plural = 'Заявки'
        indexes = [
            models.Index(fields=['status', 'assigned_to']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['client', 'status']),
            models.Index(fields=['phone']),  # Индекс для поиска по телефону
        ]
    
    def __str__(self):
        return f"Заявка #{self.id} - {self.client_name} ({self.get_status_display()})"
    
    def clean(self):
        """Валидация модели"""
        errors = {}
        
        # Проверка обязательных полей
        if not self.client_name:
            errors['client_name'] = 'Имя клиента обязательно'
        if not self.phone:
            errors['phone'] = 'Телефон обязателен'
        if not self.address:
            errors['address'] = 'Адрес обязателен'
        if not self.problem_text:
            errors['problem_text'] = 'Описание проблемы обязательно'
        
        # Проверка назначения
        if self.assigned_to and self.assigned_to.role != User.Role.MASTER:
            errors['assigned_to'] = 'Мастер должен иметь роль "Мастер"'
        
        # Проверка клиента
        if self.client and self.client.role != User.Role.CLIENT:
            errors['client'] = 'Пользователь должен быть клиентом'
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        # Автоматически подставляем имя и телефон из профиля клиента, если не указаны
        if not self.client_name and self.client:
            self.client_name = self.client.get_full_name() or self.client.username
        if not self.phone and self.client:
            self.phone = self.client.phone
        
        self.clean()
        super().save(*args, **kwargs)
    
    def can_take_work(self, user):
        """Проверка, может ли мастер взять заявку в работу"""
        return (
            self.status == self.Status.ASSIGNED and
            self.assigned_to == user and
            user.role == User.Role.MASTER
        )
    
    def can_complete(self, user):
        """Проверка, может ли мастер завершить заявку"""
        return (
            self.status == self.Status.IN_PROGRESS and
            self.assigned_to == user and
            user.role == User.Role.MASTER
        )
    
    def can_cancel(self, user):
        """Проверка, может ли пользователь отменить заявку"""
        if user.is_dispatcher:
            return True
        if user.is_client and self.client == user:
            return self.status in [self.Status.NEW, self.Status.ASSIGNED]
        return False