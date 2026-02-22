# План реализации сервисного слоя

## 1. Обзор

Реализация сервисного слоя для приложения `requests_app` с изоляцией бизнес-логики от presentation layer (views). Сервисный слой обеспечит:

- Транзакционность связанных операций
- Защиту от гонок (optimistic + pessimistic locking)
- Централизованную валидацию и проверку прав
- Аудит действий пользователей
- Тестируемость и переиспользуемость кода

---

## 2. Целевая файловая структура

```
requests_app/
├── services/
│   ├── __init__.py           # Экспорт публичных интерфейсов
│   ├── exceptions.py         # Исключения сервисного слоя
│   ├── permissions.py        # Проверки прав доступа
│   ├── validators.py        # Валидация данных и бизнес-правил
│   ├── audit.py             # Аудит действий пользователей
│   └── request_service.py   # Основной сервис заявок
├── views/
│   ├── client.py            # Рефакторинг: подключение сервиса
│   ├── dispatcher.py        # Рефакторинг: подключение сервиса
│   └── master.py            # Рефакторинг: подключение сервиса
└── ...

repair_service/
└── settings.py              # Дополнить: MAX_ACTIVE_REQUESTS_PER_MASTER
```

---

## 3. Конфигурация

### 3.1. Настройки (`repair_service/settings.py`)

Добавить в конец файла:

```python
# Сервисный слой
MAX_ACTIVE_REQUESTS_PER_MASTER = 5  # Максимум активных заявок на мастере
```

---

## 4. Исключения

### Файл: `requests_app/services/exceptions.py`

```python
"""Исключения сервисного слоя заявок."""

from typing import Optional


class RequestServiceError(Exception):
    """Базовое исключение для всех ошибок сервиса заявок."""
    pass


class RequestPermissionError(RequestServiceError):
    """Исключение при нарушении прав доступа."""
    pass


class RequestValidationError(RequestServiceError):
    """Исключение при нарушении бизнес-правил валидации.
    
    Attributes:
        message: Сообщение об ошибке.
        field: Имя поля, к которому относится ошибка (опционально).
    """
    
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message)
        self.field = field
        self.message = message
    
    def __str__(self):
        return self.message


class InvalidStatusTransitionError(RequestValidationError):
    """Исключение при попытке недопустимого перехода статуса.
    
    Attributes:
        current_status: Текущий статус.
        target_status: Целевой статус.
    """
    
    def __init__(self, current_status: str, target_status: str):
        message = f"Недопустимый переход статуса: {current_status} -> {target_status}"
        super().__init__(message)
        self.current_status = current_status
        self.target_status = target_status


class ConcurrentModificationError(RequestServiceError):
    """Исключение при конкурентном изменении заявки.
    
    Возникает при обнаружении конфликта версий (optimistic locking)
    или при попытке изменить заявку, заблокированную другим пользователем.
    """
    pass


class MasterUnavailableError(RequestValidationError):
    """Исключение при недоступности мастера.
    
    Attributes:
        master_id: ID мастера.
        reason: Причина недоступности.
    """
    
    def __init__(self, master_id: int, reason: str):
        message = f"Мастер (ID={master_id}) недоступен: {reason}"
        super().__init__(message, field='assigned_to')
        self.master_id = master_id
        self.reason = reason
```

---

## 5. Права доступа

### Файл: `requests_app/services/permissions.py`

```python
"""Проверки прав доступа к операциям с заявками."""

from typing import TYPE_CHECKING

from ..models import Request, User

if TYPE_CHECKING:
    from ..models import User


class RequestPermissions:
    """Класс для проверки прав доступа к операциям с заявками."""
    
    @staticmethod
    def can_create(user: 'User') -> bool:
        """Проверка права на создание заявки.
        
        Создавать заявки могут только клиенты.
        """
        return user.is_authenticated and user.is_client
    
    @staticmethod
    def can_view(user: 'User', request_obj: Request) -> bool:
        """Проверка права на просмотр заявки.
        
        Правила:
        - Диспетчер: видит все заявки
        - Клиент: видит только свои заявки
        - Мастер: видит только назначенные заявки
        """
        if not user.is_authenticated:
            return False
        
        if user.is_dispatcher:
            return True
        
        if user.is_client:
            return request_obj.client == user
        
        if user.is_master:
            return request_obj.assigned_to == user
        
        return False
    
    @staticmethod
    def can_view_list(user: 'User') -> bool:
        """Проверка права на просмотр списка заявок."""
        return user.is_authenticated
    
    @staticmethod
    def can_view_all(user: 'User') -> bool:
        """Проверка права на просмотр всех заявок (диспетчер)."""
        return user.is_authenticated and user.is_dispatcher
    
    @staticmethod
    def can_cancel(user: 'User', request_obj: Request) -> bool:
        """Проверка права на отмену заявки.
        
        Правила:
        - Диспетчер: может отменить любую заявку
        - Клиент: может отменить только свои заявки со статусами NEW или ASSIGNED
        """
        if not user.is_authenticated:
            return False
        
        if user.is_dispatcher:
            return True
        
        if user.is_client:
            if request_obj.client != user:
                return False
            return request_obj.status in [Request.Status.NEW, Request.Status.ASSIGNED]
        
        return False
    
    @staticmethod
    def can_assign_master(user: 'User') -> bool:
        """Проверка права на назначение мастера (диспетчер)."""
        return user.is_authenticated and user.is_dispatcher
    
    @staticmethod
    def can_reassign_master(user: 'User', request_obj: Request) -> bool:
        """Проверка права на переназначение мастера (диспетчер).
        
        Переназначить можно только заявки в статусе ASSIGNED или IN_PROGRESS.
        """
        if not user.is_dispatcher:
            return False
        return request_obj.status in [Request.Status.ASSIGNED, Request.Status.IN_PROGRESS]
    
    @staticmethod
    def can_take_work(user: 'User', request_obj: Request) -> bool:
        """Проверка права на взятие заявки в работу (мастер).
        
        Мастер может взять только новую заявку (статус NEW).
        """
        if not user.is_authenticated or not user.is_master:
            return False
        return request_obj.status == Request.Status.NEW
    
    @staticmethod
    def can_start_work(user: 'User', request_obj: Request) -> bool:
        """Проверка права на начало работы над заявкой (мастер).
        
        Мастер может начать работу только над назначенной ему заявкой
        со статусом ASSIGNED.
        """
        if not user.is_authenticated or not user.is_master:
            return False
        return (
            request_obj.status == Request.Status.ASSIGNED
            and request_obj.assigned_to == user
        )
    
    @staticmethod
    def can_complete(user: 'User', request_obj: Request) -> bool:
        """Проверка права на завершение заявки (мастер).
        
        Мастер может завершить только заявку в статусе IN_PROGRESS,
        которая назначена ему.
        """
        if not user.is_authenticated or not user.is_master:
            return False
        return (
            request_obj.status == Request.Status.IN_PROGRESS
            and request_obj.assigned_to == user
        )
    
    @staticmethod
    def can_edit(user: 'User', request_obj: Request) -> bool:
        """Проверка права на редактирование заявки (диспетчер).
        
        Редактировать можно только новые заявки (до назначения мастера).
        """
        return user.is_authenticated and user.is_dispatcher and request_obj.status == Request.Status.NEW
    
    @staticmethod
    def can_view_master_list(user: 'User') -> bool:
        """Проверка права на просмотр списка мастеров (диспетчер)."""
        return user.is_authenticated and user.is_dispatcher
```

---

## 6. Валидаторы

### Файл: `requests_app/services/validators.py`

```python
"""Валидация данных и бизнес-правил для заявок."""

from typing import Any, Dict, Optional, TYPE_CHECKING

from django.conf import settings

from ..models import Request, User
from .exceptions import (
    RequestValidationError,
    MasterUnavailableError,
)

if TYPE_CHECKING:
    from ..models import User


class RequestValidator:
    """Валидатор данных и бизнес-правил для заявок."""
    
    REQUIRED_CREATE_FIELDS = ['client_name', 'phone', 'address', 'problem_text']
    
    @classmethod
    def validate_create_data(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация данных при создании заявки.
        
        Args:
            data: Словарь с данными заявки.
            
        Returns:
            Валидированные данные.
            
        Raises:
            RequestValidationError: При нарушении правил валидации.
        """
        errors = {}
        
        for field in cls.REQUIRED_CREATE_FIELDS:
            value = data.get(field)
            if not value or (isinstance(value, str) and not value.strip()):
                errors[field] = f'Поле "{field}" обязательно для заполнения'
        
        if errors:
            raise RequestValidationError(
                f'Ошибка валидации: {", ".join(errors.keys())}'
            )
        
        phone = data.get('phone', '')
        if phone and len(phone) < 5:
            errors['phone'] = 'Номер телефона слишком короткий'
        
        if errors:
            raise RequestValidationError(
                'Ошибка валидации данных заявки',
                field=list(errors.keys())[0]
            )
        
        return data
    
    @classmethod
    def validate_assignment(
        cls,
        master: 'User',
        max_active: Optional[int] = None
    ) -> bool:
        """Валидация доступности мастера для назначения.
        
        Проверяет:
        - Мастер существует и имеет роль MASTER
        - Лимит активных заявок не превышен
        
        Args:
            master: Мастер для проверки.
            max_active: Максимальное количество активных заявок.
                       По умолчанию из настроек.
            
        Returns:
            True если мастер доступен.
            
        Raises:
            MasterUnavailableError: Если мастер недоступен.
        """
        if master.role != User.Role.MASTER:
            raise MasterUnavailableError(master.id, 'Пользователь не является мастером')
        
        max_active = max_active or settings.MAX_ACTIVE_REQUESTS_PER_MASTER
        
        active_count = Request.objects.filter(
            assigned_to=master,
            status__in=[Request.Status.ASSIGNED, Request.Status.IN_PROGRESS]
        ).count()
        
        if active_count >= max_active:
            raise MasterUnavailableError(
                master.id,
                f'Превышен лимит активных заявок ({active_count}/{max_active})'
            )
        
        return True
    
    @classmethod
    def validate_status_transition(
        cls,
        current_status: str,
        target_status: str
    ) -> bool:
        """Валидация допустимости перехода статуса.
        
        Допустимые переходы:
        - NEW -> ASSIGNED (назначение мастера)
        - ASSIGNED -> IN_PROGRESS (начало работы)
        - IN_PROGRESS -> DONE (завершение)
        - NEW -> CANCELED (отмена)
        - ASSIGNED -> CANCELED (отмена)
        - ASSIGNED -> ASSIGNED (переназначение)
        - IN_PROGRESS -> ASSIGNED (переназначение)
        
        Args:
            current_status: Текущий статус.
            target_status: Целевой статус.
            
        Returns:
            True если переход допустим.
            
        Raises:
            InvalidStatusTransitionError: Если переход недопустим.
        """
        valid_transitions = {
            Request.Status.NEW: [
                Request.Status.ASSIGNED,
                Request.Status.CANCELED,
            ],
            Request.Status.ASSIGNED: [
                Request.Status.IN_PROGRESS,
                Request.Status.CANCELED,
                Request.Status.ASSIGNED,  # Переназначение
            ],
            Request.Status.IN_PROGRESS: [
                Request.Status.DONE,
                Request.Status.ASSIGNED,  # Переназначение
            ],
            Request.Status.DONE: [],
            Request.Status.CANCELED: [],
        }
        
        allowed = valid_transitions.get(current_status, [])
        if target_status not in allowed:
            raise InvalidStatusTransitionError(current_status, target_status)
        
        return True
```

---

## 7. Аудит

### Файл: `requests_app/services/audit.py`

```python
"""Аудит действий пользователей с заявками."""

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from django.contrib.auth import get_user_model

if TYPE_CHECKING:
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    from ..models import Request

logger = logging.getLogger('requests_app.audit')


class AuditAction:
    """Константы действий для аудита."""
    
    CREATED = 'created'
    ASSIGNED = 'assigned'
    REASSIGNED = 'reassigned'
    TAKEN = 'taken'
    STARTED = 'started'
    COMPLETED = 'completed'
    CANCELED = 'canceled'
    EDITED = 'edited'


class AuditLogger:
    """Логирование действий пользователей с заявками.
    
    Текущая реализация использует Python logging.
    В будущем будет интегрирована с моделью AuditLog.
    """
    
    def __init__(self):
        self.logger = logger
    
    def log(
        self,
        user: Optional['User'],
        action: str,
        request: 'Request',
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Логирование действия с заявкой.
        
        Args:
            user: Пользователь, совершивший действие.
            action: Тип действия (из AuditAction).
            request: Заявка, над которой совершено действие.
            details: Дополнительные детали действия.
        """
        user_id = user.id if user else 'anonymous'
        username = user.username if user else 'anonymous'
        
        details_str = ''
        if details:
            details_str = f' | Details: {details}'
        
        log_message = (
            f'[AUDIT] user_id={user_id} username={username} '
            f'action={action} request_id={request.id} '
            f'status={request.status}{details_str}'
        )
        
        self.logger.info(log_message)
    
    def log_created(self, user: 'User', request: 'Request') -> None:
        """Логирование создания заявки."""
        self.log(user, AuditAction.CREATED, request)
    
    def log_assigned(
        self,
        user: 'User',
        request: 'Request',
        master_id: int
    ) -> None:
        """Логирование назначения мастера."""
        self.log(user, AuditAction.ASSIGNED, request, {'master_id': master_id})
    
    def log_reassigned(
        self,
        user: 'User',
        request: 'Request',
        old_master_id: int,
        new_master_id: int
    ) -> None:
        """Логирование переназначения мастера."""
        self.log(
            user,
            AuditAction.REASSIGNED,
            request,
            {'old_master_id': old_master_id, 'new_master_id': new_master_id}
        )
    
    def log_taken(self, user: 'User', request: 'Request') -> None:
        """Логирование взятия заявки в работу."""
        self.log(user, AuditAction.TAKEN, request)
    
    def log_started(self, user: 'User', request: 'Request') -> None:
        """Логирование начала работы."""
        self.log(user, AuditAction.STARTED, request)
    
    def log_completed(self, user: 'User', request: 'Request') -> None:
        """Логирование завершения заявки."""
        self.log(user, AuditAction.COMPLETED, request)
    
    def log_canceled(
        self,
        user: 'User',
        request: 'Request',
        old_status: str
    ) -> None:
        """Логирование отмены заявки."""
        self.log(
            user,
            AuditAction.CANCELED,
            request,
            {'old_status': old_status}
        )
    
    def log_edited(
        self,
        user: 'User',
        request: 'Request',
        changes: Dict[str, Any]
    ) -> None:
        """Логирование редактирования заявки."""
        self.log(user, AuditAction.EDITED, request, {'changes': changes})


audit_logger = AuditLogger()
```

---

## 8. Основной сервис

### Файл: `requests_app/services/request_service.py`

```python
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
            client_name=validated_data['client_name'],
            phone=validated_data['phone'],
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
    def take_work(self, request_id: int, master: 'User') -> Request:
        """Взятие заявки в работу (мастер).
        
        Мастер берет новую заявку (без назначения).
        
        Args:
            request_id: ID заявки.
            master: Мастер, берущий заявку.
            
        Returns:
            Обновленная заявка.
            
        Raises:
            RequestPermissionError: Если нет прав.
            RequestValidationError: При ошибках валидации.
            ConcurrentModificationError: При конфликте версий.
        """
        request = Request.objects.select_for_update().get(pk=request_id)
        
        if not self.permissions.can_take_work(master, request):
            raise RequestPermissionError('Нельзя взять эту заявку в работу')
        
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
        
        audit_logger.log_taken(master, request)
        
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
        for field in ['client_name', 'phone', 'address', 'problem_text']:
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
```

---

## 9. Экспорт

### Файл: `requests_app/services/__init__.py`

```python
"""Сервисный слой для работы с заявками."""

from .exceptions import (
    RequestServiceError,
    RequestPermissionError,
    RequestValidationError,
    InvalidStatusTransitionError,
    ConcurrentModificationError,
    MasterUnavailableError,
)

from .permissions import RequestPermissions

from .validators import RequestValidator

from .audit import AuditLogger, audit_logger, AuditAction

from .request_service import RequestService


__all__ = [
    # Исключения
    'RequestServiceError',
    'RequestPermissionError',
    'RequestValidationError',
    'InvalidStatusTransitionError',
    'ConcurrentModificationError',
    'MasterUnavailableError',
    # Классы
    'RequestPermissions',
    'RequestValidator',
    'AuditLogger',
    'RequestService',
    # Экземпляры
    'audit_logger',
    # Константы
    'AuditAction',
]
```

---

## 10. Рефакторинг Views

### 10.1. Client Views (`requests_app/views/client.py`)

```python
from django.views.generic import ListView, CreateView, DetailView, UpdateView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

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
        return super().form_valid(form)
```

### 10.2. Dispatcher Views (`requests_app/views/dispatcher.py`)

```python
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


class DispatcherRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.is_dispatcher


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


class RequestAssignView(DispatcherRequiredMixin, UpdateView):
    model = Request
    template_name = 'dispatcher/request_assign.html'
    fields = ['assigned_to']
    success_url = reverse_lazy('dispatcher:all-requests')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['assigned_to'].queryset = User.objects.filter(role=User.Role.MASTER)
        return form

    def get_queryset(self):
        return Request.objects.filter(status__in=[Request.Status.NEW])

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
        
        return super().form_valid(form)


class RequestReassignView(DispatcherRequiredMixin, UpdateView):
    model = Request
    template_name = 'dispatcher/request_reassign.html'
    fields = ['assigned_to']
    success_url = reverse_lazy('dispatcher:all-requests')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['assigned_to'].queryset = User.objects.filter(role=User.Role.MASTER)
        return form

    def get_queryset(self):
        return Request.objects.filter(
            status__in=[Request.Status.ASSIGNED, Request.Status.IN_PROGRESS]
        )

    def form_valid(self, form):
        new_master = form.cleaned_data['assigned_to']
        old_master = form.instance.assigned_to
        service = RequestService()
        
        try:
            service.reassign_master(form.instance.pk, new_master, self.request.user)
            old_name = old_master.get_full_name() or old_master.username if old_master else 'None'
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
        
        return super().form_valid(form)


class RequestCancelView(DispatcherRequiredMixin, UpdateView):
    model = Request
    template_name = 'dispatcher/request_cancel.html'
    fields = []
    success_url = reverse_lazy('dispatcher:all-requests')

    def get_queryset(self):
        return Request.objects.exclude(status__in=[Request.Status.DONE, Request.Status.CANCELED])

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
        except ConcurrentModificationError:
            messages.error(
                self.request,
                'Заявка была изменена другим пользователем. Обновите страницу.'
            )
            return self.form_invalid(form)
        
        return super().form_valid(form)


class MasterListView(DispatcherRequiredMixin, ListView):
    model = User
    template_name = 'dispatcher/master_list.html'
    context_object_name = 'masters'
    
    def get_queryset(self):
        return User.objects.filter(role=User.Role.MASTER)
```

### 10.3. Master Views (`requests_app/views/master.py`)

```python
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


class AvailableRequestListView(MasterRequiredMixin, ListView):
    model = Request
    template_name = 'master/available_requests.html'
    context_object_name = 'requests'
    paginate_by = 10

    def get_queryset(self):
        return Request.objects.filter(
            status__in=[Request.Status.NEW, Request.Status.ASSIGNED]
        ).exclude(assigned_to=self.request.user).order_by('-created_at')


class AssignedRequestListView(MasterRequiredMixin, ListView):
    model = Request
    template_name = 'master/assigned_requests.html'
    context_object_name = 'requests'
    paginate_by = 10

    def get_queryset(self):
        return Request.objects.filter(
            assigned_to=self.request.user
        ).order_by('-created_at')


class RequestTakeView(MasterRequiredMixin, UpdateView):
    model = Request
    template_name = 'master/request_take.html'
    fields = []
    success_url = reverse_lazy('master:assigned-requests')

    def get_queryset(self):
        return Request.objects.filter(status=Request.Status.NEW)

    def form_valid(self, form):
        service = RequestService()
        
        try:
            service.take_work(form.instance.pk, self.request.user)
            messages.success(self.request, 'Заявка взята в работу')
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
        
        return super().form_valid(form)


class RequestStartWorkView(MasterRequiredMixin, UpdateView):
    model = Request
    template_name = 'master/request_start_work.html'
    fields = []
    success_url = reverse_lazy('master:assigned-requests')

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
    success_url = reverse_lazy('master:assigned-requests')

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
```

---

## 11. Порядок реализации

### Этап 1: Подготовка
1. Создать директорию `requests_app/services/`
2. Создать пустой файл `requests_app/services/__init__.py`
3. Добавить `MAX_ACTIVE_REQUESTS_PER_MASTER = 5` в `settings.py`

### Этап 2: Исключения
4. Создать `requests_app/services/exceptions.py`

### Этап 3: Права доступа
5. Создать `requests_app/services/permissions.py`

### Этап 4: Валидаторы
6. Создать `requests_app/services/validators.py`

### Этап 5: Аудит
7. Создать `requests_app/services/audit.py`

### Этап 6: Основной сервис
8. Создать `requests_app/services/request_service.py`

### Этап 7: Экспорт
9. Обновить `requests_app/services/__init__.py`

### Этап 8: Рефакторинг Views
10. Рефакторить `requests_app/views/client.py`
11. Рефакторить `requests_app/views/dispatcher.py`
12. Рефакторить `requests_app/views/master.py`

### Этап 9: Тестирование
13. Запустить приложение и проверить основные сценарии
14. Проверить логирование действий

---

## 12. Тестирование

### Сценарии для проверки:

1. **Создание заявки клиентом** → успех
2. **Создание заявки не клиентом** → PermissionError
3. **Назначение мастера диспетчером** → успех
4. **Назначение мастера не диспетчером** → PermissionError
5. **Назначение мастера на не новую заявку** → ValidationError
6. **Превышение лимита активных заявок мастера** → MasterUnavailableError
7. **Взятие заявки мастером** → успех
8. **Начало работы мастером** → успех
9. **Завершение заявки мастером** → успех
10. **Отмена заявки клиентом (new/assigned)** → успех
11. **Отмена заявки клиентом (in_progress)** → PermissionError
12. **Отмена заявки диспетчером (любой статус)** → успех
13. **Конкурентное изменение заявки** → ConcurrentModificationError

---

## 13. Заметки

### Защита от гонок

1. **Пессимистичная блокировка** (`select_for_update()`):
   - Используется при назначении, переназначении, взятии, начале работы, завершении
   - Блокирует строку в БД до конца транзакции

2. **Оптимистичная блокировка** (поле `version`):
   - Проверяется при каждом update
   - Если версия изменилась → `ConcurrentModificationError`

### Валидация

- Валидация данных формы в `RequestValidator.validate_create_data()`
- Валидация доступности мастера в `RequestValidator.validate_assignment()`
- Валидация перехода статуса в `RequestValidator.validate_status_transition()`

### Аудит

- Текущая реализация: логирование через Python logging
- В будущем: интеграция с моделью AuditLog

### Расширение функциональности

1. **Блокировка мастера**: Добавить поле `is_blocked` в модель User и проверку в `validate_assignment()`
2. **Уведомления**: Добавить вызов уведомлений в `RequestService` после успешных операций
3. **Модель AuditLog**: Создать миграцию и интегрировать с `AuditLogger`
