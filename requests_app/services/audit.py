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
