import logging
import re
from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Request, User


PHONE_PATTERN = re.compile(r'^\+?7\d{10}$')


@receiver(pre_save, sender=User)
def validate_user_phone(sender, instance, **kwargs):
    phone = instance.phone
    
    if not phone or not phone.strip():
        raise ValidationError({'phone': 'Телефон обязателен для заполнения'})
    
    clean_phone = phone.strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    
    if not PHONE_PATTERN.match(clean_phone):
        raise ValidationError({
            'phone': 'Телефон должен быть в формате +7XXXXXXXXXX (11 цифр после +7)'
        })


@receiver(pre_save, sender=Request)
def validate_request_required_fields(sender, instance, **kwargs):
    errors = {}
    
    if not instance.address or not instance.address.strip():
        errors['address'] = 'Адрес обязателен'
    if not instance.problem_text or not instance.problem_text.strip():
        errors['problem_text'] = 'Описание проблемы обязательно'
    
    if errors:
        raise ValidationError(errors)


@receiver(pre_save, sender=Request)
def validate_client_role(sender, instance, **kwargs):
    if instance.client_id:
        try:
            client = User.objects.get(pk=instance.client_id)
            if client.role != User.Role.CLIENT:
                raise ValidationError(
                    f"Клиент должен иметь роль 'Клиент'. Текущая роль: {client.get_role_display()}"
                )
        except User.DoesNotExist:
            raise ValidationError(f"Клиент с ID={instance.client_id} не существует")


@receiver(pre_save, sender=Request)
def validate_assigned_master_role(sender, instance, **kwargs):
    if instance.assigned_to_id:
        try:
            master = User.objects.get(pk=instance.assigned_to_id)
            if master.role != User.Role.MASTER:
                raise ValidationError(
                    f"Назначить можно только мастера. Текущая роль: {master.get_role_display()}"
                )
        except User.DoesNotExist:
            raise ValidationError(f"Мастер с ID={instance.assigned_to_id} не существует")
