web: daphne datapulse.asgi:application -b 0.0.0.0 -p $PORT
worker: celery -A datapulse worker -l info -c 2
beat: celery -A datapulse beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
release: python manage.py migrate --noinput && python manage.py seed_demo
