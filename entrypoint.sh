#!/bin/sh

python manage.py migrate
python manage.py create_superuser
python manage.py create_seed_data

exec python manage.py runserver 0.0.0.0:8000
