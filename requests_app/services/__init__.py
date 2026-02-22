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
