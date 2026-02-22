import json
import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from requests_app.models import Request, User


class Command(BaseCommand):
    help = 'Creates seed data from seed_data.json'

    def handle(self, *args, **options):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        json_path = os.path.join(base_dir, 'data', 'seed_data.json')

        if not os.path.exists(json_path):
            self.stdout.write(self.style.ERROR(f'File not found: {json_path}'))
            return

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        created_users = {}
        
        for client_data in data.get('clients', []):
            username = client_data['username']
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    password=client_data['password'],
                    email=client_data.get('email', ''),
                    phone=client_data['phone'],
                    first_name=client_data.get('first_name', ''),
                    last_name=client_data.get('last_name', ''),
                    is_verified=client_data.get('is_verified', False),
                    role=User.Role.CLIENT
                )
                created_users[f'client_{client_data["id"]}' if 'id' in client_data else username] = user
                self.stdout.write(f'Created client: {username}')
            else:
                self.stdout.write(f'Client {username} already exists')

        for dispatcher_data in data.get('dispatchers', []):
            username = dispatcher_data['username']
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    password=dispatcher_data['password'],
                    email=dispatcher_data.get('email', ''),
                    phone=dispatcher_data['phone'],
                    first_name=dispatcher_data.get('first_name', ''),
                    last_name=dispatcher_data.get('last_name', ''),
                    is_verified=dispatcher_data.get('is_verified', False),
                    role=User.Role.DISPATCHER
                )
                self.stdout.write(f'Created dispatcher: {username}')
            else:
                self.stdout.write(f'Dispatcher {username} already exists')

        for master_data in data.get('masters', []):
            username = master_data['username']
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    password=master_data['password'],
                    email=master_data.get('email', ''),
                    phone=master_data['phone'],
                    first_name=master_data.get('first_name', ''),
                    last_name=master_data.get('last_name', ''),
                    is_verified=master_data.get('is_verified', False),
                    role=User.Role.MASTER
                )
                self.stdout.write(f'Created master: {username}')
            else:
                self.stdout.write(f'Master {username} already exists')

        users = {u.username: u for u in User.objects.all()}

        for request_data in data.get('requests', []):
            client_id = request_data.get('client_id')
            if client_id:
                client = User.objects.filter(id=client_id, role=User.Role.CLIENT).first()
            else:
                client = None

            assigned_to_id = request_data.get('assigned_to_id')
            if assigned_to_id:
                assigned_to = User.objects.filter(id=assigned_to_id, role=User.Role.MASTER).first()
            else:
                assigned_to = None

            if not Request.objects.filter(
                client=client,
                client_name=request_data['client_name'],
                phone=request_data['phone']
            ).exists():
                Request.objects.create(
                    client=client,
                    client_name=request_data['client_name'],
                    phone=request_data['phone'],
                    address=request_data['address'],
                    problem_text=request_data['problem_text'],
                    status=request_data.get('status', 'new'),
                    assigned_to=assigned_to
                )
                self.stdout.write(f'Created request: {request_data["client_name"]} - {request_data["problem_text"][:30]}...')
            else:
                self.stdout.write(f'Request for {request_data["client_name"]} already exists')

        self.stdout.write(self.style.SUCCESS('Seed data created successfully!'))
