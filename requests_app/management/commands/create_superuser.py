from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings


class Command(BaseCommand):
    help = 'Creates superuser from environment variables'

    def handle(self, *args, **options):
        User = get_user_model()

        username = getattr(settings, 'ADMIN_USERNAME', None)
        email = getattr(settings, 'ADMIN_EMAIL', None)
        password = getattr(settings, 'ADMIN_PASSWORD', None)

        if not username or not email or not password:
            self.stdout.write(self.style.ERROR('ADMIN_USERNAME, ADMIN_EMAIL, and ADMIN_PASSWORD must be set in settings'))
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(f'Superuser {username} already exists')
            return

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            phone='+79000000000'
        )
        self.stdout.write(f'Created superuser: {username}')
