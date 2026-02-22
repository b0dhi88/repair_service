from django.core.management.base import BaseCommand
from django.test import Client
from django.urls import reverse


class Command(BaseCommand):
    help = 'Test login for each role'

    def handle(self, *args, **options):
        roles = [
            ('client', 'testuser'),
            ('master', 'master1'),
            ('dispatcher', 'dispatcher1'),
        ]
        client = Client()

        for role, username in roles:
            with self.subtest(role=role):
                response = client.post(
                    '/login/',
                    {'username': username, 'password': 'testuser123'},
                )
                if response.status_code in [200, 302, 301]:
                    self.stdout.write(self.style.SUCCESS(f'{role}: OK'))
                else:
                    self.stdout.write(self.style.ERROR(f'{role}: FAIL ({response.status_code})'))
