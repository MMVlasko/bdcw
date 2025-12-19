from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone
from django.db import connection
from core.models import AuthToken, User
from goals.models import Goal, GoalProgress
from habits.models import Habit, HabitLog
from rest_framework.permissions import BasePermission


class HasValidToken(BasePermission):
    def has_permission(self, request, view):
        if request.auth is None:
            raise AuthenticationFailed('Токен не найден')
        if not request.auth.is_active:
            raise AuthenticationFailed('Токен деактивирован')

        if request.auth.expires_at < timezone.now():
            request.auth.is_active = False
            request.auth.save()
            raise AuthenticationFailed('Токен истек')
        return bool(request.user and request.auth)

    def has_object_permission(self, request, view, obj):
        return not hasattr(obj, 'is_public') or obj.is_public or request.user.role == 'admin'


class IsAdminOrSelf(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.auth)

    def has_object_permission(self, request, view, obj):
        if type(obj) is HabitLog:
            habit = Habit.objects.filter(id=obj.habit_id).first()
            return habit.user == request.user
        if type(obj) is GoalProgress:
            goal = Goal.objects.filter(id=obj.goal_id).first()
            return goal.user == request.user
        return ((type(obj) is User and obj.id == request.user.id) or
                (type(obj) in (Goal, Habit) and obj.user_id == request.user.id) or
                request.user.role == 'admin')


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.role == 'admin')


class TokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        token_key = request.headers.get('Authorization', '')

        if not token_key:
            return None

        try:
            token = AuthToken.objects.get(key=token_key)
            token.last_used = timezone.now()
            token.save()

            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT set_config(\'app.user_id\', %s, false)',
                    [str(token.user.id)]
                )

            return token.user, token

        except AuthToken.DoesNotExist:
            raise AuthenticationFailed('Неверный токен')
        except Exception as e:
            raise AuthenticationFailed(f'Ошибка аутентификации: {str(e)}')

    def authenticate_header(self, request):
        return 'Token'
