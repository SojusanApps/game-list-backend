#!/bin/sh

case "$1" in
    gunicorn)
        uv run gunicorn -c gunicorn.conf.py game_list.game_list.wsgi:application
    ;;
    set_state)
        uv run django-admin collectstatic --no-input && \
        uv run django-admin migrate --no-input
    ;;
    celery_worker)
        uv run celery -A game_list.game_list worker -l info
    ;;
    celery_beat)
        uv run celery -A game_list.game_list beat -l info --pidfile=/tmp/celerybeat.pid
    ;;
    keycloak_events_consumer)
        exec uv run django-admin consume_keycloak_events
    ;;
    *)
        exec "$@"
    ;;
esac
