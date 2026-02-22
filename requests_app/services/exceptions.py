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
