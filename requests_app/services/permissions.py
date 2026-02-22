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
