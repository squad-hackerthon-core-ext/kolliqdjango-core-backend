web: gunicorn --workers 3 --bind 0.0.0.0:$PORT --timeout 120 kolliq.wsgi:application
worker: celery -A kolliq worker --loglevel=info --concurrency=2
