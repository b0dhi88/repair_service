from django.core.management.base import BaseCommand
from django.contrib import messages


class Command(BaseCommand):
    help = 'Creates 8 test messages for testing message queue UI'

    def handle(self, *args, **options):
        # Note: Django messages are stored in session, not database.
        # This command is for reference only. To test the message queue,
        # use the test_messages view or create a request with messages.
        
        test_messages = [
            ('info', 'Это тестовое информационное сообщение №1'),
            ('success', 'Успешное действие выполнено! №2'),
            ('warning', 'Внимание! Предупреждение №3'),
            ('error', 'Произошла ошибка №4'),
            ('info', 'Информационное сообщение №5'),
            ('success', 'Данные сохранены успешно №6'),
            ('warning', 'Срок действия истекает скоро №7'),
            ('error', 'Ошибка валидации данных №8'),
        ]
        
        self.stdout.write(self.style.SUCCESS('Test messages created:'))
        for tag, msg in test_messages:
            self.stdout.write(f'  [{tag}] {msg}')
        
        self.stdout.write('')
        self.stdout.write('To test the message queue UI, use the test_messages view:')
        self.stdout.write('  curl -L http://localhost:8000/test/messages/')
        self.stdout.write('')
        self.stdout.write('Or add messages to any view using:')
        self.stdout.write('  messages.info(request, "Your message")')
        self.stdout.write('  messages.success(request, "Your message")')
        self.stdout.write('  messages.warning(request, "Your message")')
        self.stdout.write('  messages.error(request, "Your message")')
