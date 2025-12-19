from django.db import connection


class AuditUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        with connection.cursor() as cursor:
            cursor.execute('RESET app.user_id')

        return response
