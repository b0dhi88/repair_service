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
    
    REQUIRED_CREATE_FIELDS = ['address', 'problem_text']
    
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
            max_active: Максимальное количество активных заак.
                       По умолчанию из настроек.
        
        Returns:
            True если мастер доступен.
        
        Raises:
            MasterUnavailableError: Если мастер недоступен.
        """
        if master is None:
            raise RequestValidationError('Мастер обязателен для назначения')
        
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
