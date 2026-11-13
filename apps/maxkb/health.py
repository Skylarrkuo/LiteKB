from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django_redis import get_redis_connection
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError


@require_GET
def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        get_redis_connection("default").ping()
    except (DatabaseError, SQLAlchemyError, RedisError, OSError):
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
