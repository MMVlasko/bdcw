from datetime import datetime, date

from django.db import IntegrityError, connection, transaction
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from audit.models import BatchLog
from bdcw.authentication import TokenAuthentication, HasValidToken, IsAdminOrSelf, IsAdmin
from bdcw.error_responses import (BAD_REQUEST_RESPONSE, UNAUTHORIZED_RESPONSE, FORBIDDEN_RESPONSE, NOT_FOUND_RESPONSE,
                                  INTERNAL_SERVER_ERROR, BAD_BATCH_REQUEST_RESPONSE)
from categories.models import Category
from core.serializers import BatchOperationLogSerializer
from .models import Habit, HabitLog
from core.models import User
from .serializers import HabitSerializer, HabitCreateSerializer, HabitUpdateSerializer, HabitPartialUpdateSerializer, \
    HabitLogSerializer, HabitLogCreateSerializer, HabitLogUpdateSerializer, HabitLogPartialUpdateSerializer, \
    BatchHabitCreateSerializer, BatchHabitLogCreateSerializer
from rest_framework.pagination import LimitOffsetPagination


class HabitLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 10
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 100


class HabitViewSet(viewsets.ModelViewSet):
    queryset = Habit.objects.all()
    pagination_class = HabitLimitOffsetPagination
    authentication_classes = [TokenAuthentication]

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'user_habits', 'category_habits']:
            return [HasValidToken()]

        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [HasValidToken(), IsAdminOrSelf()]

        return [HasValidToken()]

    def get_queryset(self):
        user = self.request.user

        if self.action == 'list':
            if user.role != User.UserRole.ADMIN:
                return Habit.objects.filter(is_public=True)

        return super().get_queryset()

    def get_serializer_class(self):
        return {
            'create': HabitCreateSerializer,
            'update': HabitUpdateSerializer,
            'partial_update': HabitPartialUpdateSerializer,
        }.get(self.action, HabitSerializer)

    @extend_schema(
        summary="Получить список привычек",
        description="""
            Получение списка привычек

            Возвращает список всех привычек с пагинацией.

            Особенности:
            - Администраторы видят все привычки
            - Обычные пользователи видят только привычки с is_public=True

            Права доступа:
            - Требуется действительный токен

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            """,
        parameters=[
            OpenApiParameter(
                name='limit',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Количество записей на странице (макс. 100)',
                required=False,
                default=10
            ),
            OpenApiParameter(
                name='offset',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Смещение от начала списка',
                required=False,
                default=0
            )
        ],
        responses={
            200: OpenApiResponse(
                response=HabitSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Список привычек",
                        summary="Стандартный ответ со списком привычек",
                        value={
                            "count": 25,
                            "next": "http://127.0.0.1:8080/api/habits/?limit=10&offset=10",
                            "previous": None,
                            "results": [
                                {
                                    "id": 1,
                                    "user_id": 123,
                                    "title": "Утренняя зарядка",
                                    "description": "Ежедневные упражнения",
                                    "category_id": 5,
                                    "frequency_type": 1,
                                    "frequency_value": 7,
                                    "is_active": True,
                                    "is_public": True,
                                    "created_at": "2024-01-10T09:15:30Z",
                                    "updated_at": "2024-01-15T14:20:45Z"
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name="Пустой список привычек",
                        summary="Когда привычек нет",
                        value={
                            "count": 0,
                            "next": None,
                            "previous": None,
                            "results": []
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Привычки']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Создать привычку",
        description="""
            Создание новой привычки

            Создает новую привычку для пользователя.

            Права доступа:
            - Требуется действительный токен
            - Пользователь может создать привычку только для себя
            - Администратор может создать привычку для любого пользователя

            Обязательные поля:
            - user: ID пользователя (владельца привычки)
            - title: Название привычки (строка, максимум 255 символов)
            - category: ID категории
            - frequency_type: Тип частоты (целое положительное число)
            - frequency_value: Значение частоты (целое положительное число)
            - is_active: Активна ли привычка (булево значение)
            - is_public: Видна ли привычка публично (булево значение)

            Опциональные поля:
            - description: Описание привычки (текст, может быть null)

            Особенности:
            - Проверяется существование пользователя и категории
            """,
        request=HabitCreateSerializer,
        responses={
            201: OpenApiResponse(
                response=HabitSerializer,
                description='Created',
                examples=[
                    OpenApiExample(
                        name="Привычка успешно создана",
                        summary="Стандартный ответ при успешном создании",
                        value={
                            "id": 45,
                            "user_id": 123,
                            "title": "Чтение книг",
                            "description": "Читать 30 минут в день",
                            "category_id": 3,
                            "frequency_type": 1,
                            "frequency_value": 7,
                            "is_active": True,
                            "is_public": False,
                            "created_at": "2024-01-15T10:30:00Z",
                            "updated_at": "2024-01-15T10:30:00Z"
                        }
                    )
                ]
            ),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Привычки']
    )
    def create(self, request, *args, **kwargs):
        if request.data['user'] != request.user.id and request.user.role != User.UserRole.ADMIN:
            raise PermissionDenied('Нельзя создать привычку у другого пользователя')
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Получить информацию о привычке",
        description="""
            Получение информации о привычке

            Возвращает полную информацию о конкретной привычке по её ID.

            Права доступа:
            - Требуется действительный токен
            - Владелец привычки может видеть любую информацию о своей привычке
            - Администратор может видеть информацию о любой привычке
            - Обычные пользователи могут видеть только публичные привычки

            Возвращаемые поля:
            - id: Идентификатор привычки
            - user_id: ID пользователя-владельца
            - title: Название привычки
            - description: Описание привычки
            - category_id: ID категории
            - frequency_type: Тип частоты
            - frequency_value: Значение частоты
            - is_active: Активна ли привычка
            - is_public: Видна ли привычка публично
            - created_at: Дата создания
            - updated_at: Дата обновления
            """,
        responses={
            200: OpenApiResponse(
                response=HabitSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Публичная привычка",
                        summary="Информация о публичной привычке",
                        value={
                            "id": 1,
                            "user_id": 123,
                            "title": "Бег по утрам",
                            "description": "Пробежка 5 км каждое утро",
                            "category_id": 2,
                            "frequency_type": 1,
                            "frequency_value": 7,
                            "is_active": True,
                            "is_public": True,
                            "created_at": "2024-01-10T09:15:30Z",
                            "updated_at": "2024-01-15T14:20:45Z"
                        }
                    ),
                    OpenApiExample(
                        name="Приватная привычка",
                        summary="Информация о приватной привычке (только для владельца/админа)",
                        value={
                            "id": 2,
                            "user_id": 123,
                            "title": "Личные заметки",
                            "description": "Ежедневное ведение дневника",
                            "category_id": 4,
                            "frequency_type": 1,
                            "frequency_value": 7,
                            "is_active": True,
                            "is_public": False,
                            "created_at": "2024-01-12T11:45:20Z",
                            "updated_at": "2024-01-15T16:30:00Z"
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Привычки']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Обновить информацию о привычке",
        description="""
            Полное обновление информации о привычке

            Заменяет все данные привычки новыми значениями. Все поля обязательны.

            Права доступа:
            - Требуется действительный токен
            - Владелец привычки может обновлять только свою привычку
            - Администратор может обновлять любую привычку

            Обязательные поля:
            - title: Название привычки
            - description: Описание привычки (может быть null)
            - frequency_type: Тип частоты
            - frequency_value: Значение частоты
            - is_active: Активна ли привычка
            - is_public: Видна ли привычка публично

            Валидация:
            - Проверка обязательных полей
            - Проверка типов данных
            - Проверка прав доступа

            Особенности:
            - Поле user_id обновить нельзя
            - Поле category_id обновить нельзя
            - Поле updated_at обновляется автоматически
            """,
        request=HabitUpdateSerializer,
        responses={
            200: OpenApiResponse(
                response=HabitSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Привычка успешно обновлена",
                        summary="Стандартный ответ при успешном обновлении",
                        value={
                            "id": 1,
                            "user_id": 123,
                            "title": "Обновленное название",
                            "description": "Обновленное описание привычки",
                            "category_id": 2,
                            "frequency_type": 2,
                            "frequency_value": 14,
                            "is_active": True,
                            "is_public": True,
                            "created_at": "2024-01-10T09:15:30Z",
                            "updated_at": "2024-01-15T15:30:00Z"
                        }
                    )
                ]
            ),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Привычки']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Частично обновить информацию о привычке",
        description="""
            Частичное обновление информации о привычке

            Обновляет только указанные поля привычки. Не указанные поля остаются без изменений.

            Права доступа:
            - Требуется действительный токен
            - Владелец привычки может обновлять только свою привычку
            - Администратор может обновлять любую привычку

            Доступные для обновления поля:
            - title: Название привычки
            - description: Описание привычки (можно установить в null)
            - frequency_type: Тип частоты
            - frequency_value: Значение частоты
            - is_active: Активна ли привычка
            - is_public: Видна ли привычка публично

            Особенности:
            - Можно обновлять любое подмножество полей
            - Не требуется передавать все поля
            - Нельзя изменить user_id и category_id
            """,
        request=HabitPartialUpdateSerializer,
        responses={
            200: OpenApiResponse(
                response=HabitSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Обновлено только описание",
                        summary="Обновлено одно поле",
                        value={
                            "id": 1,
                            "user_id": 123,
                            "title": "Бег по утрам",
                            "description": "Новое подробное описание",
                            "category_id": 2,
                            "frequency_type": 1,
                            "frequency_value": 7,
                            "is_active": True,
                            "is_public": True,
                            "created_at": "2024-01-10T09:15:30Z",
                            "updated_at": "2024-01-15T15:45:00Z"
                        }
                    ),
                    OpenApiExample(
                        name="Обновлено несколько полей",
                        summary="Обновлены title и is_active",
                        value={
                            "id": 2,
                            "user_id": 123,
                            "title": "Новое название",
                            "description": "Старое описание",
                            "category_id": 3,
                            "frequency_type": 1,
                            "frequency_value": 7,
                            "is_active": False,
                            "is_public": True,
                            "created_at": "2024-01-12T11:45:20Z",
                            "updated_at": "2024-01-15T15:45:00Z"
                        }
                    )
                ]
            ),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Привычки']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Удалить привычку",
        description="""
            Удаление привычки

            Полностью удаляет привычку и все связанные логи привычки из системы.

            Права доступа:
            - Требуется действительный токен
            - Владелец привычки может удалить только свою привычку
            - Администратор может удалить любую привычку

            Последствия удаления:
            - Безвозвратное удаление привычки
            - Каскадное удаление всех связанных логов привычки
            """,
        responses={
            204: OpenApiResponse(
                description='No Content'
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Привычки']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Получить привычки пользователя",
        description="""
            Получение привычек пользователя

            Получить список всех привычек конкретного пользователя по его ID.

            Права доступа:
            - Требуется действительный токен
            - Пользователь может просматривать свои привычки (все)
            - Администратор может просматривать привычки любого пользователя (все)
            - Обычные пользователи могут просматривать только публичные привычки других пользователей

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            """,
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID пользователя, чьи привычки запрашиваются'
            ),
            OpenApiParameter(
                name='limit',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Количество записей на странице (макс. 100)',
                required=False,
                default=10
            ),
            OpenApiParameter(
                name='offset',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Смещение от начала списка',
                required=False,
                default=0
            )
        ],
        responses={
            200: OpenApiResponse(
                response=HabitSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Список привычек пользователя",
                        summary="Стандартный ответ со списком привычек",
                        value={
                            "count": 8,
                            "next": None,
                            "previous": None,
                            "results": [
                                {
                                    "id": 1,
                                    "user_id": 123,
                                    "title": "Утренняя зарядка",
                                    "description": "Ежедневные упражнения",
                                    "category_id": 5,
                                    "frequency_type": 1,
                                    "frequency_value": 7,
                                    "is_active": True,
                                    "is_public": True,
                                    "created_at": "2024-01-10T09:15:30Z",
                                    "updated_at": "2024-01-15T14:20:45Z"
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name="Пустой список привычек",
                        summary="Когда у пользователя нет привычек",
                        value={
                            "count": 0,
                            "next": None,
                            "previous": None,
                            "results": []
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Привычки']
    )
    @action(detail=False, methods=['get'], url_path='user/(?P<user_id>[^/.]+)')
    def user_habits(self, request, user_id=None):
        user = get_object_or_404(User, id=user_id)

        current_user = request.user

        if current_user.id == user.id or current_user.role == User.UserRole.ADMIN:
            habits = Habit.objects.filter(user=user)
        else:
            habits = Habit.objects.filter(user=user, is_public=True)

        page = self.paginate_queryset(habits)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(habits, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Получить привычки по категории",
        description="""
            Получение привычек по категории

            Получить список всех привычек с конкретной категорией по её ID.

            Права доступа:
            - Требуется действительный токен
            - Администратор может просматривать все привычки категории
            - Обычные пользователи могут просматривать только публичные привычки категории

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            """,
        parameters=[
            OpenApiParameter(
                name='category_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID категории, по которой запрашиваются привычки'
            ),
            OpenApiParameter(
                name='limit',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Количество записей на странице (макс. 100)',
                required=False,
                default=10
            ),
            OpenApiParameter(
                name='offset',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Смещение от начала списка',
                required=False,
                default=0
            )
        ],
        responses={
            200: OpenApiResponse(
                response=HabitSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Список привычек категории",
                        summary="Стандартный ответ со списком привычек",
                        value={
                            "count": 15,
                            "next": "http://127.0.0.1:8080/api/habits/category/5/?limit=10&offset=10",
                            "previous": None,
                            "results": [
                                {
                                    "id": 3,
                                    "user_id": 456,
                                    "title": "Чтение книг",
                                    "description": "30 минут в день",
                                    "category_id": 5,
                                    "frequency_type": 1,
                                    "frequency_value": 7,
                                    "is_active": True,
                                    "is_public": True,
                                    "created_at": "2024-01-12T11:45:20Z",
                                    "updated_at": "2024-01-15T16:30:00Z"
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name="Пустой список привычек",
                        summary="Когда в категории нет привычек",
                        value={
                            "count": 0,
                            "next": None,
                            "previous": None,
                            "results": []
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Привычки']
    )
    @action(detail=False, methods=['get'], url_path='category/(?P<category_id>[^/.]+)')
    def category_habits(self, request, category_id=None):
        category = get_object_or_404(Category, id=category_id)

        current_user = request.user

        if current_user.role == User.UserRole.ADMIN:
            habits = Habit.objects.filter(category=category)
        else:
            habits = Habit.objects.filter(category=category, is_public=True)

        page = self.paginate_queryset(habits)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(habits, many=True)
        return Response(serializer.data)


class HabitLogViewSet(viewsets.ModelViewSet):
    queryset = HabitLog.objects.all()
    pagination_class = HabitLimitOffsetPagination
    authentication_classes = [TokenAuthentication]

    def get_permissions(self):
        if self.action in ['retrieve', 'habit_logs']:
            return [HasValidToken()]

        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [HasValidToken(), IsAdminOrSelf()]
        elif self.action in ['list']:
            return [IsAdmin()]

        return [HasValidToken()]

    def get_serializer_class(self):
        return {
            'create': HabitLogCreateSerializer,
            'update': HabitLogUpdateSerializer,
            'partial_update': HabitLogPartialUpdateSerializer,
        }.get(self.action, HabitLogSerializer)

    @extend_schema(
        summary="Список логов соблюдения привычки",
        description="""
            Получение списка логов соблюдения привычки

            Получить список всех логов соблюдения привычек по всем привычкам всех пользователей.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут просматривать все логи привычек

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            """,
        parameters=[
            OpenApiParameter(
                name='limit',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Количество записей на странице (макс. 100)',
                required=False,
                default=10
            ),
            OpenApiParameter(
                name='offset',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Смещение от начала списка',
                required=False,
                default=0
            )
        ],
        responses={
            200: OpenApiResponse(
                response=HabitLogSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Список логов привычек",
                        summary="Стандартный ответ со списком логов",
                        value={
                            "count": 150,
                            "next": "http://127.0.0.1:8080/api/habit-logs/?limit=10&offset=10",
                            "previous": None,
                            "results": [
                                {
                                    "id": 1,
                                    "habit_id": 5,
                                    "log_date": "2024-01-15",
                                    "status": "completed",
                                    "notes": "Выполнено успешно",
                                    "created_at": "2024-01-15T09:30:00Z",
                                    "updated_at": "2024-01-15T09:30:00Z"
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name="Пустой список логов",
                        summary="Когда логов привычек нет",
                        value={
                            "count": 0,
                            "next": None,
                            "previous": None,
                            "results": []
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Логи соблюдения привычки']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Создать новый лог соблюдения привычки",
        description="""
            Создание нового лога соблюдения привычки

            Создает новый лог выполнения привычки.

            Права доступа:
            - Требуется действительный токен
            - Пользователь может создать лог только для своих привычек
            - Администратор может создать лог для любой привычки

            Обязательные поля:
            - habit: ID привычки
            - log_date: Дата лога (в формате YYYY-MM-DD)
            - status: Статус выполнения (completed, skipped, failed)

            Опциональные поля:
            - notes: Примечания к выполнению (текст, может быть null)
            """,
        request=HabitLogCreateSerializer,
        responses={
            201: OpenApiResponse(
                response=HabitLogSerializer,
                description='Created',
                examples=[
                    OpenApiExample(
                        name="Лог привычки успешно создан",
                        summary="Стандартный ответ при успешном создании",
                        value={
                            "id": 45,
                            "habit_id": 3,
                            "log_date": "2024-01-15",
                            "status": "completed",
                            "notes": "Выполнено успешно",
                            "created_at": "2024-01-15T10:30:00Z",
                            "updated_at": "2024-01-15T10:30:00Z"
                        }
                    )
                ]
            ),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Логи соблюдения привычки']
    )
    def create(self, request, *args, **kwargs):
        habit = Habit.objects.filter(id=request.data['habit']).first()
        if habit.user != request.user and request.user.role != User.UserRole.ADMIN:
            raise PermissionDenied('Нельзя создать лог привычки у другого пользователя')
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Получить лог соблюдения привычки",
        description="""
            Получение информации о логе соблюдения привычки

            Возвращает полную информацию о конкретном логе привычки по его ID.

            Права доступа:
            - Требуется действительный токен
            - Владелец привычки может видеть лог своей привычки
            - Администратор может видеть любой лог привычки
            - Обычные пользователи могут видеть логи публичных привычек

            Возвращаемые поля:
            - id: Идентификатор лога
            - habit_id: ID привычки
            - log_date: Дата лога
            - status: Статус выполнения
            - notes: Примечания
            - created_at: Дата создания лога
            - updated_at: Дата обновления лога
            """,
        responses={
            200: OpenApiResponse(
                response=HabitLogSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Лог привычки",
                        summary="Информация о логе привычки",
                        value={
                            "id": 1,
                            "habit_id": 3,
                            "log_date": "2024-01-15",
                            "status": "completed",
                            "notes": "Выполнено успешно",
                            "created_at": "2024-01-15T09:30:00Z",
                            "updated_at": "2024-01-15T09:30:00Z"
                        }
                    ),
                    OpenApiExample(
                        name="Лог с пропуском",
                        summary="Лог со статусом skipped",
                        value={
                            "id": 2,
                            "habit_id": 3,
                            "log_date": "2024-01-14",
                            "status": "skipped",
                            "notes": "Был занят",
                            "created_at": "2024-01-14T09:30:00Z",
                            "updated_at": "2024-01-14T09:30:00Z"
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Логи соблюдения привычки']
    )
    def retrieve(self, request, *args, **kwargs):
        habit = Habit.objects.filter(id=request.data['habit']).first()
        if habit.user != request.user and not habit.is_public and request.user.role != User.UserRole.ADMIN:
            raise PermissionDenied('Нельзя получить лог приватной привычки у другого пользователя')
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Обновить лог соблюдения привычки",
        description="""
            Полное обновление информации о логе соблюдения привычки

            Заменяет все данные лога привычки новыми значениями. Все поля обязательны.

            Права доступа:
            - Требуется действительный токен
            - Владелец привычки может обновлять только лог своей привычки
            - Администратор может обновлять любой лог привычки

            Обязательные поля:
            - log_date: Дата лога (в формате YYYY-MM-DD)
            - status: Статус выполнения (completed, skipped, failed)
            - notes: Примечания (может быть null)

            Валидация:
            - Проверка обязательных полей
            - Проверка формата даты
            - Проверка допустимых значений статуса
            - Проверка прав доступа
            - Поле habit_id обновить нельзя
            """,
        request=HabitLogUpdateSerializer,
        responses={
            200: OpenApiResponse(
                response=HabitLogSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Лог привычки успешно обновлен",
                        summary="Стандартный ответ при успешном обновлении",
                        value={
                            "id": 1,
                            "habit_id": 3,
                            "log_date": "2024-01-16",
                            "status": "skipped",
                            "notes": "Перенес на завтра",
                            "created_at": "2024-01-15T09:30:00Z",
                            "updated_at": "2024-01-15T15:30:00Z"
                        }
                    )
                ]
            ),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Логи соблюдения привычки']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Частично обновить лог соблюдения привычки",
        description="""
            Частичное обновление информации о логе соблюдения привычки

            Обновляет только указанные поля лога привычки. Не указанные поля остаются без изменений.

            Права доступа:
            - Требуется действительный токен
            - Владелец привычки может обновлять только лог своей привычки
            - Администратор может обновлять любой лог привычки

            Доступные для обновления поля:
            - log_date: Дата лога (в формате YYYY-MM-DD)
            - status: Статус выполнения (completed, skipped, failed)
            - notes: Примечания (можно установить в null)

            Особенности:
            - Можно обновлять любое подмножество полей
            - Не требуется передавать все поля
            - Поле updated_at обновляется автоматически
            - Нельзя изменить habit_id
            """,
        request=HabitLogPartialUpdateSerializer,
        responses={
            200: OpenApiResponse(
                response=HabitLogSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Обновлен только статус",
                        summary="Обновлено одно поле",
                        value={
                            "id": 1,
                            "habit_id": 3,
                            "log_date": "2024-01-15",
                            "status": "failed",
                            "notes": "Выполнено успешно",
                            "created_at": "2024-01-15T09:30:00Z",
                            "updated_at": "2024-01-15T15:45:00Z"
                        }
                    ),
                    OpenApiExample(
                        name="Обновлены дата и примечания",
                        summary="Обновлено несколько полей",
                        value={
                            "id": 2,
                            "habit_id": 3,
                            "log_date": "2024-01-14",
                            "status": "skipped",
                            "notes": "Новые примечания",
                            "created_at": "2024-01-14T09:30:00Z",
                            "updated_at": "2024-01-15T15:45:00Z"
                        }
                    )
                ]
            ),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Логи соблюдения привычки']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Удалить лог соблюдения привычки",
        description="""
            Удаление лога соблюдения привычки

            Полностью удаляет лог выполнения привычки из системы.

            Права доступа:
            - Требуется действительный токен
            - Владелец привычки может удалить только лог своей привычки
            - Администратор может удалить любой лог привычки

            Последствия удаления:
            - Безвозвратное удаление лога привычки
            """,
        responses={
            204: OpenApiResponse(
                description='No Content'
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Логи соблюдения привычки']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Получить логи соблюдения привычки",
        description="""
            Получение логов соблюдения привычки

            Получить список всех логов по конкретной привычке по её ID.

            Права доступа:
            - Требуется действительный токен
            - Владелец привычки может просматривать все логи своей привычки
            - Администратор может просматривать логи любой привычки
            - Обычные пользователи могут просматривать логи публичных привычек

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            """,
        parameters=[
            OpenApiParameter(
                name='habit_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID привычки, чьи логи запрашиваются'
            ),
            OpenApiParameter(
                name='limit',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Количество записей на странице (макс. 100)',
                required=False,
                default=10
            ),
            OpenApiParameter(
                name='offset',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Смещение от начала списка',
                required=False,
                default=0
            )
        ],
        responses={
            200: OpenApiResponse(
                response=HabitLogSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Список логов привычки",
                        summary="Стандартный ответ со списком логов",
                        value={
                            "count": 30,
                            "next": "http://127.0.0.1:8080/api/habit-logs/habit/3/?limit=10&offset=10",
                            "previous": None,
                            "results": [
                                {
                                    "id": 15,
                                    "habit_id": 3,
                                    "log_date": "2024-01-15",
                                    "status": "completed",
                                    "notes": "Выполнено успешно",
                                    "created_at": "2024-01-15T09:30:00Z",
                                    "updated_at": "2024-01-15T09:30:00Z"
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name="Пустой список логов",
                        summary="Когда у привычки нет логов",
                        value={
                            "count": 0,
                            "next": None,
                            "previous": None,
                            "results": []
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Логи соблюдения привычки']
    )
    @action(detail=False, methods=['get'], url_path='habit/(?P<habit_id>[^/.]+)')
    def habit_logs(self, request, habit_id=None):
        habit = get_object_or_404(Habit, id=habit_id)
        if request.user == habit.user or request.user.role == User.UserRole.ADMIN or habit.is_public:
            habit_logs = HabitLog.objects.filter(habit=habit)
        else:
            raise PermissionDenied('Нет доступа к приватным привычкам')

        page = self.paginate_queryset(habit_logs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(habit_logs, many=True)
        return Response(serializer.data)


class BatchHabitCreateView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken, IsAdmin]

    @extend_schema(
        summary="Батчевая загрузка привычек",
        description="""
            Массовое создание привычек

            Создание нескольких привычек за одну операцию с использованием bulk_create.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут создавать привычки батчами

            Обязательные поля для каждой привычки:
            - user_id: ID пользователя-владельца
            - title: Название привычки (строка, максимум 255 символов)
            - category_id: ID категории
            - frequency_type: Тип частоты (целое положительное число)
            - frequency_value: Значение частоты (целое положительное число)

            Опциональные поля:
            - description: Описание привычки (текст, может быть null)
            - is_active: Активна ли привычка (по умолчанию: true)
            - is_public: Видна ли привычка публично (по умолчанию: true)

            Ограничения:
            - Максимум 10,000 привычек за запрос
            - batch_size от 1 до 5,000
            - user_id и category_id должны существовать
            - title должен быть уникальным для каждого пользователя
            - frequency_type и frequency_value должны быть положительными числами
            """,
        request=BatchHabitCreateSerializer,
        responses={
            200: OpenApiResponse(
                response=BatchOperationLogSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Полностью успешная операция",
                        summary="Все привычки созданы",
                        value={
                            "total_processed": 100,
                            "successful": 100,
                            "failed": 0,
                            "batch_size": 50,
                            "errors": [],
                            "created_ids": [101, 102, 103, 104, 105],
                            "batches_processed": 2
                        }
                    ),
                    OpenApiExample(
                        name="Операция с ошибками",
                        summary="Некоторые привычки не созданы",
                        value={
                            "total_processed": 5,
                            "successful": 3,
                            "failed": 2,
                            "batch_size": 100,
                            "errors": [
                                {
                                    "data": {
                                        "user_id": 123,
                                        "title": "Бег по утрам",
                                        "category_id": 2,
                                        "frequency_type": 1,
                                        "frequency_value": 7
                                    },
                                    "error": "Привычка с title 'Бег по утрам' для пользователя 123 уже существует",
                                    "type": "duplicate_error"
                                },
                                {
                                    "data": {
                                        "user_id": 999,
                                        "title": "Чтение",
                                        "category_id": 3,
                                        "frequency_type": 1,
                                        "frequency_value": 7
                                    },
                                    "error": "Пользователь с ID 999 не существует",
                                    "type": "reference_error"
                                }
                            ],
                            "created_ids": [106, 107, 108],
                            "batches_processed": 1
                        }
                    )
                ]
            ),
            400: BAD_BATCH_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Привычки']
    )
    def post(self, request):
        serializer = BatchHabitCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Ошибка валидации',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        habits_data = serializer.validated_data['habits']
        batch_size = serializer.validated_data['batch_size']

        operation_log = {
            'total_processed': len(habits_data),
            'successful': 0,
            'failed': 0,
            'errors': [],
            'created_ids': [],
            'batches_processed': 0,
            'batch_size': batch_size
        }

        try:
            validated_habits_data = []
            seen_combinations = set()

            user_ids = User.objects.values_list('id', flat=True)
            category_ids = Category.objects.values_list('id', flat=True)

            for i, habit_data in enumerate(habits_data):
                try:
                    processed_data = habit_data.copy()

                    required_fields = ['user_id', 'title', 'frequency_type', 'frequency_value', 'category_id']
                    missing_fields = []

                    for field in required_fields:
                        if field not in processed_data:
                            missing_fields.append(field)

                    if missing_fields:
                        raise ValueError(f"Обязательные поля отсутствуют: {', '.join(missing_fields)}")

                    user_id = processed_data['user_id']
                    title = processed_data['title']
                    frequency_type = processed_data['frequency_type']
                    frequency_value = processed_data['frequency_value']
                    category_id = processed_data['category_id']

                    if not isinstance(title, str):
                        raise ValueError(f"title должен быть строкой, получено: {title}")

                    title = title.strip()
                    if not title:
                        raise ValueError("title не может быть пустой строкой")

                    if isinstance(user_id, str):
                        try:
                            processed_data['user_id'] = int(user_id)
                        except ValueError:
                            raise ValueError(f"user_id должен быть целым числом, получено: {user_id}")
                    elif not isinstance(user_id, int):
                        raise ValueError(f"user_id должен быть целым числом, получено: {user_id}")

                    if isinstance(category_id, str):
                        try:
                            processed_data['category_id'] = int(category_id)
                        except ValueError:
                            raise ValueError(f"category_id должен быть целым числом, получено: {category_id}")
                    elif not isinstance(category_id, int):
                        raise ValueError(f"category_id должен быть целым числом, получено: {category_id}")

                    # frequency_type - integer not null
                    if isinstance(frequency_type, str):
                        try:
                            processed_data['frequency_type'] = int(frequency_type)
                        except ValueError:
                            raise ValueError(f"frequency_type должен быть целым числом, получено: {frequency_type}")
                    elif not isinstance(frequency_type, int):
                        raise ValueError(f"frequency_type должен быть целым числом, получено: {frequency_type}")

                    if processed_data['frequency_type'] <= 0:
                        raise ValueError(f"frequency_type должен быть целым положительным числом,"
                                         f" получено: {frequency_type}")

                    if isinstance(frequency_value, str):
                        try:
                            processed_data['frequency_value'] = int(frequency_value)
                        except ValueError:
                            raise ValueError(f"frequency_value должен быть целым числом, получено: {frequency_value}")
                    elif not isinstance(frequency_value, int):
                        raise ValueError(f"frequency_value должен быть целым числом, получено: {frequency_value}")

                    if processed_data['frequency_value'] <= 0:
                        raise ValueError(f"frequency_value должен быть целым положительным числом,"
                                         f" получено: {frequency_value}")

                    combination = f"{processed_data['user_id']}:{title}"
                    if combination in seen_combinations:
                        raise ValueError(
                            f"Привычка с title '{title}' для пользователя {user_id} дублируется в запросе")
                    seen_combinations.add(combination)

                    if processed_data['user_id'] not in user_ids:
                        raise ValueError(f"Пользователь с ID {processed_data['user_id']} не существует")

                    if processed_data['category_id'] not in category_ids:
                        raise ValueError(f"Категория с ID {category_id} не существует")

                    if 'is_active' in processed_data:
                        is_active = processed_data['is_active']
                        if not isinstance(is_active, bool):
                            raise ValueError(f"is_active должен быть булевым значением, получено: {is_active}")
                    else:
                        processed_data['is_active'] = True

                    if 'is_public' in processed_data:
                        is_public = processed_data['is_public']
                        if not isinstance(is_public, bool):
                            raise ValueError(f"is_public должен быть булевым значением, получено: {is_public}")
                    else:
                        processed_data['is_public'] = True

                    # description - text (может быть null)
                    if 'description' in processed_data and processed_data['description'] is not None:
                        if not isinstance(processed_data['description'], str):
                            raise ValueError(
                                f"description должен быть строкой, получено: {processed_data['description']}")

                    validated_habits_data.append({
                        'index': i,
                        'data': processed_data,
                        'user_id': processed_data['user_id'],
                        'title': title
                    })

                except serializers.ValidationError as e:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': habit_data,
                        'error': e.detail,
                        'type': 'validation_error'
                    })
                except Exception as e:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': habit_data,
                        'error': str(e),
                        'type': 'validation_error'
                    })

            if not validated_habits_data:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            habit_identifiers = []
            for item in validated_habits_data:
                habit_identifiers.append({
                    'user_id': item['user_id'],
                    'title': item['title']
                })

            existing_habits = {}
            if habit_identifiers:
                q_objects = Q()
                for identifier in habit_identifiers:
                    q_objects |= Q(
                        user_id=identifier['user_id'],
                        title=identifier['title']
                    )

                existing_qs = Habit.objects.filter(q_objects)
                for habit in existing_qs:
                    key = f"{habit.user_id}:{habit.title}"
                    existing_habits[key] = habit

            filtered_habits = []

            for item in validated_habits_data:
                user_id = item['user_id']
                title = item['title']
                key = f"{user_id}:{title}"

                if key in existing_habits:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': item['data'],
                        'error': f'Привычка с title "{title}" для пользователя {user_id} уже существует',
                        'type': 'duplicate_error'
                    })
                else:
                    filtered_habits.append(item)

            if not filtered_habits:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            user_ids = set()
            category_ids = set()

            for item in filtered_habits:
                data = item['data']
                user_ids.add(data['user_id'])
                category_ids.add(data['category_id'])

            users_dict = {user.id: user for user in User.objects.filter(id__in=user_ids)}
            categories_dict = {cat.id: cat for cat in Category.objects.filter(id__in=category_ids)}

            # Проверка наличия всех пользователей
            missing_users = user_ids - set(users_dict.keys())
            if missing_users:
                for item in filtered_habits:
                    if item['data']['user_id'] in missing_users:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'data': item['data'],
                            'error': f'Пользователь с ID {item["data"]["user_id"]} не существует',
                            'type': 'reference_error'
                        })
                filtered_habits = [
                    item for item in filtered_habits
                    if item['data']['user_id'] not in missing_users
                ]

            missing_categories = category_ids - set(categories_dict.keys())
            if missing_categories:
                for item in filtered_habits:
                    if item['data']['category_id'] in missing_categories:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'data': item['data'],
                            'error': f'Категория с ID {item["data"]["category_id"]} не существует',
                            'type': 'reference_error'
                        })
                filtered_habits = [
                    item for item in filtered_habits
                    if item['data']['category_id'] not in missing_categories
                ]

            if not filtered_habits:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            batches = [
                filtered_habits[i:i + batch_size]
                for i in range(0, len(filtered_habits), batch_size)
            ]

            for batch_index, batch in enumerate(batches):
                habits_to_create = []

                for item in batch:
                    habit_data = dict(item['data'])

                    try:
                        user = users_dict[habit_data['user_id']]
                        category = categories_dict[habit_data['category_id']]

                        habit = Habit(
                            user=user,
                            title=habit_data['title'],
                            description=habit_data.get('description'),
                            category=category,
                            frequency_type=habit_data['frequency_type'],
                            frequency_value=habit_data['frequency_value'],
                            is_active=habit_data['is_active'],
                            is_public=habit_data['is_public'],
                            created_at=timezone.now(),
                            updated_at=timezone.now()
                        )

                        habits_to_create.append(habit)
                    except KeyError as e:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'data': habit_data,
                            'error': f'Ошибка при создании привычки: {str(e)}',
                            'type': 'creation_error'
                        })
                    except Exception as e:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'data': habit_data,
                            'error': f'Ошибка при создании привычки: {str(e)}',
                            'type': 'creation_error'
                        })

                with connection.cursor() as cursor:
                    cursor.execute("ALTER TABLE habits DISABLE TRIGGER audit_habits_trigger")

                try:
                    with transaction.atomic():
                        if habits_to_create:
                            try:
                                created = Habit.objects.bulk_create(
                                    habits_to_create,
                                    batch_size=len(habits_to_create)
                                )
                                operation_log['successful'] += len(created)

                                if created:
                                    created_ids = [habit.id for habit in created]
                                    operation_log['created_ids'].extend(created_ids)

                            except IntegrityError as e:
                                operation_log['failed'] += len(habits_to_create)
                                operation_log['errors'].append({
                                    'type': 'integrity_error',
                                    'error': 'Ошибка целостности при bulk_create',
                                    'details': str(e)
                                })
                                raise
                            except Exception as e:
                                operation_log['failed'] += len(habits_to_create)
                                operation_log['errors'].append({
                                    'type': 'bulk_create_error',
                                    'error': str(e)
                                })

                finally:
                    with connection.cursor() as cursor:
                        cursor.execute("ALTER TABLE habits ENABLE TRIGGER audit_habits_trigger")

                operation_log['batches_processed'] += 1

        except Exception as e:
            operation_log['errors'].append({
                'type': 'critical',
                'error': str(e)
            })
            operation_log['failed'] = operation_log['total_processed'] - operation_log['successful']

        batch_log = BatchLog(
            table_name='habits',
            changed_by=request.user,
            total_processed=operation_log['total_processed'],
            successful=operation_log['successful'],
            failed=operation_log['failed'],
            errors=operation_log['errors'],
            created_ids=operation_log['created_ids'],
            batches_processed=operation_log['batches_processed'],
            batch_size=operation_log['batch_size']
        )
        batch_log.save()

        response_serializer = BatchOperationLogSerializer(operation_log)
        return Response(response_serializer.data)


class BatchHabitLogCreateView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken, IsAdmin]

    @extend_schema(
        summary="Батчевая загрузка логов привычек",
        description="""
            Массовое создание логов привычек

            Создание нескольких логов привычек за одну операцию с использованием bulk_create.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут создавать логи привычек батчами

            Обязательные поля для каждого лога привычки:
            - habit_id: ID привычки
            - log_date: Дата лога (в формате YYYY-MM-DD)
            - status: Статус выполнения (completed, skipped, failed)

            Опциональные поля:
            - notes: Примечания к выполнению (текст, может быть null)

            Ограничения:
            - Максимум 10,000 логов за запрос
            - batch_size от 1 до 5,000
            - habit_id должен существовать
            - log_date должен быть в правильном формате
            - status должен быть одним из допустимых значений
            """,
        request=BatchHabitLogCreateSerializer,
        responses={
            200: OpenApiResponse(
                response=BatchOperationLogSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Полностью успешная операция",
                        summary="Все логи созданы",
                        value={
                            "total_processed": 50,
                            "successful": 50,
                            "failed": 0,
                            "batch_size": 25,
                            "errors": [],
                            "created_ids": [201, 202, 203, 204, 205],
                            "batches_processed": 2
                        }
                    ),
                    OpenApiExample(
                        name="Операция с ошибками",
                        summary="Некоторые логи не созданы",
                        value={
                            "total_processed": 5,
                            "successful": 3,
                            "failed": 2,
                            "batch_size": 100,
                            "errors": [
                                {
                                    "data": {
                                        "habit_id": 3,
                                        "log_date": "2024-01-15",
                                        "status": "completed"
                                    },
                                    "error": "Привычка с ID 3 не существует",
                                    "type": "reference_error"
                                },
                                {
                                    "data": {
                                        "habit_id": 5,
                                        "log_date": "неправильная дата",
                                        "status": "completed"
                                    },
                                    "error": "log_date должен быть в формате YYYY-MM-DD, получено: неправильная дата",
                                    "type": "validation_error"
                                }
                            ],
                            "created_ids": [206, 207, 208],
                            "batches_processed": 1
                        }
                    )
                ]
            ),
            400: BAD_BATCH_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Логи соблюдения привычки']
    )
    def post(self, request):
        serializer = BatchHabitLogCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Ошибка валидации',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        habit_logs_data = serializer.validated_data['habit_logs']
        batch_size = serializer.validated_data['batch_size']

        operation_log = {
            'total_processed': len(habit_logs_data),
            'successful': 0,
            'failed': 0,
            'errors': [],
            'created_ids': [],
            'batches_processed': 0,
            'batch_size': batch_size
        }

        try:
            validated_habit_logs_data = []

            habit_ids = Habit.objects.values_list('id', flat=True)

            for i, habit_log_data in enumerate(habit_logs_data):
                try:
                    processed_data = habit_log_data.copy()

                    required_fields = ['habit_id', 'log_date', 'status']
                    missing_fields = []

                    for field in required_fields:
                        if field not in processed_data:
                            missing_fields.append(field)

                    if missing_fields:
                        raise ValueError(f"Обязательные поля отсутствуют: {', '.join(missing_fields)}")

                    habit_id = processed_data['habit_id']
                    log_date = processed_data['log_date']
                    status_value = processed_data['status']

                    if isinstance(habit_id, str):
                        try:
                            processed_data['habit_id'] = int(habit_id)
                        except ValueError:
                            raise ValueError(f"habit_id должен быть целым числом, получено: {habit_id}")
                    elif not isinstance(habit_id, int):
                        raise ValueError(f"habit_id должен быть целым числом, получено: {habit_id}")

                    # status - varchar(20) not null
                    if not isinstance(status_value, str):
                        raise ValueError(f"status должен быть строкой, получено: {status_value}")

                    status_value = status_value.strip()
                    if not status_value:
                        raise ValueError("status не может быть пустой строкой")

                    valid_statuses = ['completed', 'skipped', 'failed']
                    if status_value not in valid_statuses:
                        raise ValueError(f"status должен быть одним из: {', '.join(valid_statuses)}, "
                                         f"получено: {status_value}")

                    if isinstance(log_date, str):
                        try:
                            processed_data['log_date'] = datetime.strptime(log_date, '%Y-%m-%d').date()
                        except ValueError:
                            raise ValueError(f"log_date должен быть в формате YYYY-MM-DD, получено: {log_date}")
                    elif not isinstance(log_date, date):
                        raise ValueError(f"log_date должен быть датой, получено: {log_date}")

                    if processed_data['habit_id'] not in habit_ids:
                        raise ValueError(f"Привычка с ID {processed_data['habit_id']} не существует")

                    # notes - text (может быть null)
                    if 'notes' in processed_data and processed_data['notes'] is not None:
                        if not isinstance(processed_data['notes'], str):
                            raise ValueError(
                                f"notes должен быть строкой, получено: {processed_data['notes']}")

                    validated_habit_logs_data.append({
                        'index': i,
                        'data': processed_data,
                        'habit_id': processed_data['habit_id'],
                        'log_date': processed_data['log_date']
                    })

                except serializers.ValidationError as e:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': habit_log_data,
                        'error': e.detail,
                        'type': 'validation_error'
                    })
                except Exception as e:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': habit_log_data,
                        'error': str(e),
                        'type': 'validation_error'
                    })

            if not validated_habit_logs_data:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            habit_ids_set = set()

            for item in validated_habit_logs_data:
                data = item['data']
                habit_ids_set.add(data['habit_id'])

            habits_dict = {habit.id: habit for habit in Habit.objects.filter(id__in=habit_ids_set)}

            missing_habits = habit_ids_set - set(habits_dict.keys())
            if missing_habits:
                for item in validated_habit_logs_data:
                    if item['data']['habit_id'] in missing_habits:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'data': item['data'],
                            'error': f'Привычка с ID {item["data"]["habit_id"]} не существует',
                            'type': 'reference_error'
                        })
                validated_habit_logs_data = [
                    item for item in validated_habit_logs_data
                    if item['data']['habit_id'] not in missing_habits
                ]

            if not validated_habit_logs_data:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            batches = [
                validated_habit_logs_data[i:i + batch_size]
                for i in range(0, len(validated_habit_logs_data), batch_size)
            ]

            for batch_index, batch in enumerate(batches):
                habit_logs_to_create = []

                for item in batch:
                    habit_log_data = item['data']

                    try:
                        habit = habits_dict[habit_log_data['habit_id']]

                        habit_log = HabitLog(
                            habit=habit,
                            log_date=habit_log_data['log_date'],
                            status=habit_log_data['status'],
                            notes=habit_log_data.get('notes'),  # может быть null
                            created_at=timezone.now(),
                            updated_at=timezone.now()
                        )

                        habit_logs_to_create.append(habit_log)
                    except KeyError as e:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'data': habit_log_data,
                            'error': f'Ошибка при создании лога привычки: {str(e)}',
                            'type': 'creation_error'
                        })
                    except Exception as e:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'data': habit_log_data,
                            'error': f'Ошибка при создании лога привычки: {str(e)}',
                            'type': 'creation_error'
                        })

                with connection.cursor() as cursor:
                    cursor.execute("ALTER TABLE habit_logs DISABLE TRIGGER audit_habit_logs_trigger")

                try:
                    with transaction.atomic():
                        if habit_logs_to_create:
                            try:
                                created = HabitLog.objects.bulk_create(
                                    habit_logs_to_create,
                                    batch_size=len(habit_logs_to_create)
                                )
                                operation_log['successful'] += len(created)

                                if created:
                                    created_ids = [habit_log.id for habit_log in created]
                                    operation_log['created_ids'].extend(created_ids)

                            except IntegrityError as e:
                                operation_log['failed'] += len(habit_logs_to_create)
                                operation_log['errors'].append({
                                    'type': 'integrity_error',
                                    'error': 'Ошибка целостности при bulk_create',
                                    'details': str(e)
                                })
                                raise
                            except Exception as e:
                                operation_log['failed'] += len(habit_logs_to_create)
                                operation_log['errors'].append({
                                    'type': 'bulk_create_error',
                                    'error': str(e)
                                })

                finally:
                    with connection.cursor() as cursor:
                        cursor.execute("ALTER TABLE habit_logs ENABLE TRIGGER audit_habit_logs_trigger")

                operation_log['batches_processed'] += 1

        except Exception as e:
            operation_log['errors'].append({
                'type': 'critical',
                'error': str(e)
            })
            operation_log['failed'] = operation_log['total_processed'] - operation_log['successful']

        batch_log = BatchLog(
            table_name='habit_logs',
            changed_by=request.user,
            total_processed=operation_log['total_processed'],
            successful=operation_log['successful'],
            failed=operation_log['failed'],
            errors=operation_log['errors'],
            created_ids=operation_log['created_ids'],
            batches_processed=operation_log['batches_processed'],
            batch_size=operation_log['batch_size']
        )
        batch_log.save()

        response_serializer = BatchOperationLogSerializer(operation_log)
        return Response(response_serializer.data)
