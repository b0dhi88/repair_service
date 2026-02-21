from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings


class Command(BaseCommand):
    help = 'Creates initial users for the application'

    def handle(self, *args, **options):
        User = get_user_model()

        admin_username = getattr(settings, 'ADMIN_USERNAME', None)
        admin_email = getattr(settings, 'ADMIN_EMAIL', None)
        admin_password = getattr(settings, 'ADMIN_PASSWORD', None)

        if admin_username and admin_email and admin_password:
            if not User.objects.filter(username=admin_username).exists():
                User.objects.create_superuser(
                    username=admin_username,
                    email=admin_email,
                    password=admin_password
                )
                self.stdout.write(f'Created superuser: {admin_username}')
            else:
                self.stdout.write(f'Superuser {admin_username} already exists')
        else:
            self.stdout.write(self.style.WARN('ADMIN_USERNAME, ADMIN_EMAIL, or ADMIN_PASSWORD not set in settings'))

        if not User.objects.filter(username='testuser').exists():
            User.objects.create_user(
                username='testuser',
                email='testuser@test.com',
                password='testuser123'
            )
            self.stdout.write('Created test user: testuser')
        else:
            self.stdout.write('Test user already exists')
