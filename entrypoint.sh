#!/bin/sh

python manage.py migrate
python manage.py create_initial_users

exec python manage.py runserver 0.0.0.0:8000
