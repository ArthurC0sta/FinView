from django.db import connection
from django.http import JsonResponse


def health_check(request):
    """Confirma que a aplicação e sua conexão principal estão disponíveis."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        return JsonResponse({'status': 'unavailable'}, status=503)

    return JsonResponse({'status': 'ok'})
