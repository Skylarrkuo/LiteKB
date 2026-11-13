#!/bin/sh
set -eu

role_file=/opt/maxkb-app/tmp/service-role
case "${1:-api}" in
    api)
        printf 'api\n' > "$role_file"
        export SERVER_NAME=web
        echo 'LiteKB API: applying database migrations'
        python apps/manage.py migrate --noinput
        echo 'LiteKB API: collecting console static files'
        python apps/manage.py collectstatic --noinput --verbosity 0
        echo 'LiteKB API: starting WSGI workers'
        exec gunicorn maxkb.wsgi.web:application --bind 0.0.0.0:8080 \
            --workers "${LITEKB_WEB_WORKERS:-2}" --threads "${LITEKB_WEB_THREADS:-4}" \
            --timeout "${LITEKB_WEB_TIMEOUT:-120}" --access-logfile - --error-logfile - --capture-output
        ;;
    worker)
        printf 'worker\n' > "$role_file"
        export SERVER_NAME=celery C_FORCE_ROOT=1
        rm -f /opt/maxkb-app/tmp/worker_ready_celery /opt/maxkb-app/tmp/worker_heartbeat_celery
        exec celery -A ops.celery:app worker --hostname=celery@%h --queues=celery,model --pool=threads \
            --concurrency="${LITEKB_WORKER_CONCURRENCY:-4}" --heartbeat-interval=5 --loglevel=INFO
        ;;
    local-model)
        if [ "${LITEKB_LOCAL_MODEL:-0}" != 1 ]; then
            echo 'Rebuild with LITEKB_LOCAL_MODEL=1 before starting local-model.' >&2
            exit 2
        fi
        printf 'local-model\n' > "$role_file"
        export SERVER_NAME=local_model
        exec gunicorn maxkb.wsgi.model:application --bind 0.0.0.0:11636 --workers 1 --threads 2 --timeout 300
        ;;
    health)
        case "$(cat "$role_file")" in
            worker)
                exec python -c 'from pathlib import Path; from time import time; d=Path("/opt/maxkb-app/tmp"); exit(0 if (d/"worker_ready_celery").is_file() and time()-(d/"worker_heartbeat_celery").stat().st_mtime < 35 else 1)'
                ;;
            api) port=8080 ;;
            local-model) port=11636 ;;
            *) exit 1 ;;
        esac
        exec python -c 'from sys import argv; from urllib.request import urlopen; urlopen("http://127.0.0.1:"+argv[1]+"/health/ready", timeout=4).read()' "$port"
        ;;
    *) exec "$@" ;;
esac
