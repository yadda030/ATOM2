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

echo "Running static collect"
python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3