#!/bin/sh

python manage.py migrate
python manage.py create_superuser
python manage.py create_seed_data
python manage.py create_test_messages

exec python manage.py runserver 0.0.0.0:8000
