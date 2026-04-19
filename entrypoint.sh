#!/bin/sh

echo "Waiting for database..."

python << 'EOF'
import socket
import time
import os

host = "db"
port = 5432

while True:
    try:
        with socket.create_connection((host, port), timeout=2):
            print("Database is up.")
            break
    except OSError:
        time.sleep(1)
EOF

echo "Running migrations..."
python manage.py migrate --noinput

echo "Setting up initial data..."
python manage.py shell << 'EOF'
# VMIDLock singleton
from apps.ranges.models import VMIDLock
VMIDLock.objects.get_or_create(pk=1)

# SiteSettings singleton
from apps.ranges.models import SiteSettings
SiteSettings.objects.get_or_create(pk=1)

# Celery Beat periodic task
from django_celery_beat.models import PeriodicTask, IntervalSchedule
schedule, _ = IntervalSchedule.objects.get_or_create(
    every=30,
    period=IntervalSchedule.SECONDS,
)
PeriodicTask.objects.get_or_create(
    name='Poll all users',
    defaults={
        'task': 'apps.proxmox.tasks.poll_all_users',
        'interval': schedule,
        'enabled': True,
    }
)
print("Initial data setup complete.")
EOF

echo "Running static collect..."
python manage.py collectstatic --noinput

echo "Starting Daphne..."
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application