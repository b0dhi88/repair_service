"""Основной сервис для работы с заявками."""

from typing import Any, Dict, Optional, TYPE_CHECKING

from django.db import models, transaction
from django.utils import timezone

from ..models import Request, User
from .audit import audit_logger, AuditAction
from .exceptions import (
    RequestPermissionError,
    RequestValidationError,
    InvalidStatusTransitionError,
    ConcurrentModificationError,
    MasterUnavailableError,
)
from .permissions import RequestPermissions
from .validators import RequestValidator

if TYPE_CHECKING:
    from django.contrib.auth import get_user_model
    
    User = get_user_model()


class RequestService:
    """Сервис для работы с заявками.
    
    Инкапсулирует бизнес-логику, транзакции и проверки прав.
    """
    
    def __init__(
        self,
        permissions: Optional[RequestPermissions] = None,
        validator: Optional[RequestValidator] = None
    ):
        """Инициализация сервиса.
        
        Args:
            permissions: Экземпляр класса проверки прав.
                        По умолчанию создается новый.
            validator: Экземпляр валидатора.
                      По умолчанию создается новый.
        """
        self.permissions = permissions or RequestPermissions()
        self.validator = validator or RequestValidator()
    
    @transaction.atomic
    def create_request(
        self,
        client: 'User',
        data: Dict[str, Any]
    ) -> Request:
        """Создание новой заявки.
        
        Args:
            client: Клиент, создающий заявку.
            data: Данные заявки.
            
        Returns:
            Созданная заявка.
            
        Raises:
            RequestPermissionError: Если нет прав на создание.
            RequestValidationError: При ошибках валидации.
        """
        if not self.permissions.can_create(client):
            raise RequestPermissionError('Нет прав на создание заявки')
        
        validated_data = self.validator.validate_create_data(data)
        
        request = Request.objects.create(
            client=client,
            address=validated_data['address'],
            problem_text=validated_data['problem_text'],
            status=Request.Status.NEW,
        )
        
        audit_logger.log_created(client, request)
        
        return request
    
    @transaction.atomic
    def assign_master(
        self,
        request_id: int,
        master: 'User',
        dispatcher: 'User'
    ) -> Request:
        """Назначение мастера на заявку.
        
        Args:
            request_id: ID заявки.
            master: Мастер для назначения.
            dispatcher: Диспетчер, выполняющий назначение.
            
        Returns:
            Обновленная заявка.
            
        Raises:
            RequestPermissionError: Если нет прав.
            RequestValidationError: При ошибках валидации.
            ConcurrentModificationError: При конфликте версий.
        """
        if not self.permissions.can_assign_master(dispatcher):
            raise RequestPermissionError('Нет прав на назначение мастера')
        
        request = Request.objects.select_for_update().get(pk=request_id)
        
        if request.status != Request.Status.NEW:
            raise RequestValidationError(
                'Можно назначать только новые заявки',
                field='status'
            )
        
        self.validator.validate_assignment(master)
        
        updated = Request.objects.filter(
            pk=request_id,
            version=request.version
        ).update(
            assigned_to=master,
            status=Request.Status.ASSIGNED,
            version=models.F('version') + 1,
            updated_at=timezone.now()
        )
        
        if not updated:
            raise ConcurrentModificationError(
                'Заявка была изменена другим пользователем'
            )
        
        request.refresh_from_db()
        
        audit_logger.log_assigned(dispatcher, request, master.id)
        
        return request
    
    @transaction.atomic
    def reassign_master(
        self,
        request_id: int,
        new_master: 'User',
        dispatcher: 'User'
    ) -> Request:
        """Переназначение мастера на заявке.
        
        Args:
            request_id: ID заявки.
            new_master: Новый мастер.
            dispatcher: Диспетчер, выполняющий переназначение.
            
        Returns:
            Обновленная заявка.
            
        Raises:
            RequestPermissionError: Если нет прав.
            RequestValidationError: При ошибках валидации.
            ConcurrentModificationError: При конфликте версий.
        """
        request = Request.objects.select_for_update().get(pk=request_id)
        
        if not self.permissions.can_reassign_master(dispatcher, request):
            raise RequestPermissionError('Нельзя переназначить заявку в текущем статусе')
        
        old_master_id = request.assigned_to.id if request.assigned_to else None
        
        self.validator.validate_assignment(new_master)
        
        new_status = Request.Status.ASSIGNED
        
        updated = Request.objects.filter(
            pk=request_id,
            version=request.version
        ).update(
            assigned_to=new_master,
            status=new_status,
            version=models.F('version') + 1,
            updated_at=timezone.now()
        )
        
        if not updated:
            raise ConcurrentModificationError(
                'Заявка была изменена другим пользователем'
            )
        
        request.refresh_from_db()
        
        audit_logger.log_reassigned(
            dispatcher, request,
            old_master_id, new_master.id
        )
        
        return request
    
    @transaction.atomic
    def start_work(self, request_id: int, master: 'User') -> Request:
        """Начало работы над заявкой (мастер).
        
        Переводит заявку из статуса ASSIGNED в IN_PROGRESS.
        
        Args:
            request_id: ID заявки.
            master: Мастер, начинающий работу.
            
        Returns:
            Обновленная заявка.
            
        Raises:
            RequestPermissionError: Если нет прав.
            ConcurrentModificationError: При конфликте версий.
        """
        request = Request.objects.select_for_update().get(pk=request_id)
        
        if not self.permissions.can_start_work(master, request):
            raise RequestPermissionError('Нельзя начать работу над этой заявкой')
        
        self.validator.validate_status_transition(
            request.status,
            Request.Status.IN_PROGRESS
        )
        
        updated = Request.objects.filter(
            pk=request_id,
            version=request.version
        ).update(
            status=Request.Status.IN_PROGRESS,
            version=models.F('version') + 1,
            updated_at=timezone.now()
        )
        
        if not updated:
            raise ConcurrentModificationError(
                'Заявка была изменена другим пользователем'
            )
        
        request.refresh_from_db()
        
        audit_logger.log_started(master, request)
        
        return request
    
    @transaction.atomic
    def complete(self, request_id: int, master: 'User') -> Request:
        """Завершение заявки (мастер).
        
        Переводит заявку из статуса IN_PROGRESS в DONE.
        
        Args:
            request_id: ID заявки.
            master: Мастер, завершающий работу.
            
        Returns:
            Обновленная заявка.
            
        Raises:
            RequestPermissionError: Если нет прав.
            ConcurrentModificationError: При конфликте версий.
        """
        request = Request.objects.select_for_update().get(pk=request_id)
        
        if not self.permissions.can_complete(master, request):
            raise RequestPermissionError('Нельзя завершить эту заявку')
        
        self.validator.validate_status_transition(
            request.status,
            Request.Status.DONE
        )
        
        updated = Request.objects.filter(
            pk=request_id,
            version=request.version
        ).update(
            status=Request.Status.DONE,
            version=models.F('version') + 1,
            updated_at=timezone.now()
        )
        
        if not updated:
            raise ConcurrentModificationError(
                'Заявка была изменена другим пользователем'
            )
        
        request.refresh_from_db()
        
        audit_logger.log_completed(master, request)
        
        return request
    
    @transaction.atomic
    def cancel(self, request_id: int, user: 'User') -> Request:
        """Отмена заявки.
        
        Args:
            request_id: ID заявки.
            user: Пользователь, отменяющий заявку.
            
        Returns:
            Обновленная заявка.
            
        Raises:
            RequestPermissionError: Если нет прав.
            ConcurrentModificationError: При конфликте версий.
        """
        request = Request.objects.select_for_update().get(pk=request_id)
        
        if not self.permissions.can_cancel(user, request):
            raise RequestPermissionError('Нельзя отменить эту заявку')
        
        if request.status in [Request.Status.DONE, Request.Status.CANCELED]:
            raise RequestValidationError(
                'Нельзя отменить заявку в статусе DONE или CANCELED'
            )
        
        old_status = request.status
        
        updated = Request.objects.filter(
            pk=request_id,
            version=request.version
        ).update(
            status=Request.Status.CANCELED,
            version=models.F('version') + 1,
            updated_at=timezone.now()
        )
        
        if not updated:
            raise ConcurrentModificationError(
                'Заявка была изменена другим пользователем'
            )
        
        request.refresh_from_db()
        
        audit_logger.log_canceled(user, request, old_status)
        
        return request
    
    @transaction.atomic
    def edit_request(
        self,
        request_id: int,
        user: 'User',
        data: Dict[str, Any]
    ) -> Request:
        """Редактирование заявки (диспетчер).
        
        Доступно только для заявок в статусе NEW.
        
        Args:
            request_id: ID заявки.
            user: Диспетчер, редактирующий заявку.
            data: Новые данные заявки.
            
        Returns:
            Обновленная заявка.
            
        Raises:
            RequestPermissionError: Если нет прав.
            RequestValidationError: При ошибках валидации.
            ConcurrentModificationError: При конфликте версий.
        """
        request = Request.objects.select_for_update().get(pk=request_id)
        
        if not self.permissions.can_edit(user, request):
            raise RequestPermissionError('Нельзя редактировать эту заявку')
        
        validated_data = self.validator.validate_create_data(data)
        
        changes = {}
        for field in ['address', 'problem_text']:
            if field in validated_data:
                old_value = getattr(request, field)
                new_value = validated_data[field]
                if old_value != new_value:
                    changes[field] = {'old': old_value, 'new': new_value}
                    setattr(request, field, new_value)
        
        if not changes:
            return request
        
        request.save()
        
        audit_logger.log_edited(user, request, changes)
        
        return request
