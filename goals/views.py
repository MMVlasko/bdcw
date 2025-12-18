from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from django.db import connection, transaction, IntegrityError
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView

from audit.models import BatchLog
from bdcw.authentication import TokenAuthentication, HasValidToken, IsAdminOrSelf, IsAdmin
from bdcw.error_responses import (BAD_REQUEST_RESPONSE, UNAUTHORIZED_RESPONSE, FORBIDDEN_RESPONSE, NOT_FOUND_RESPONSE,
                                  INTERNAL_SERVER_ERROR, BAD_BATCH_REQUEST_RESPONSE)
from categories.models import Category
from core.serializers import BatchOperationLogSerializer
from .models import Goal, GoalProgress
from core.models import User
from .serializers import GoalSerializer, GoalCreateSerializer, GoalPartialUpdateSerializer, GoalUpdateSerializer, \
    GoalProgressSerializer, GoalProgressCreateSerializer, GoalProgressUpdateSerializer, \
    GoalProgressPartialUpdateSerializer, BatchGoalCreateSerializer, BatchGoalProgressCreateSerializer
from rest_framework.pagination import LimitOffsetPagination


class GoalLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 10
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 100


class GoalViewSet(viewsets.ModelViewSet):
    queryset = Goal.objects.all()
    pagination_class = GoalLimitOffsetPagination
    authentication_classes = [TokenAuthentication]

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'user_goals', 'category_goals']:
            return [HasValidToken()]

        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [HasValidToken(), IsAdminOrSelf()]

        return [HasValidToken()]

    def get_queryset(self):
        user = self.request.user

        if self.action == 'list':
            if user.role != User.UserRole.ADMIN:
                return Goal.objects.filter(is_public=True)

        return super().get_queryset()

    def get_serializer_class(self):
        return {
            'create': GoalCreateSerializer,
            'update': GoalUpdateSerializer,
            'partial_update': GoalPartialUpdateSerializer,
        }.get(self.action, GoalSerializer)

    @extend_schema(
        summary="Получить список целей",
        description="""
            Получение списка целей

            Возвращает список всех целей с пагинацией.

            Особенности:
            - Администраторы видят все цели
            - Обычные пользователи видят только цели с is_public=True
            - Результаты упорядочены по дате создания (новые первыми)

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
                response=GoalSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Список целей",
                        summary="Стандартный ответ со списком целей",
                        value={
                            "count": 25,
                            "next": "http://127.0.0.1:8080/api/goals/?limit=10&offset=10",
                            "previous": None,
                            "results": [
                                {
                                    "id": 1,
                                    "user_id": 123,
                                    "title": "Похудение на 5 кг",
                                    "description": "Снижение веса до 70 кг",
                                    "category_id": 3,
                                    "target_value": "5.000",
                                    "deadline": "2024-06-30",
                                    "is_completed": False,
                                    "is_public": True,
                                    "created_at": "2024-01-10T09:15:30Z",
                                    "updated_at": "2024-01-15T14:20:45Z"
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name="Пустой список целей",
                        summary="Когда целей нет",
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
        tags=['Цели']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Создать цель",
        description="""
            Создание новой цели

            Создает новую цель для пользователя.

            Права доступа:
            - Требуется действительный токен
            - Пользователь может создать цель только для себя
            - Администратор может создать цель для любого пользователя

            Обязательные поля:
            - user: ID пользователя (владельца цели)
            - title: Название цели (строка, максимум 255 символов)
            - category: ID категории
            - target_value: Целевое значение (число с точностью до 3 знаков после запятой)
            - deadline: Дата завершения цели (в формате YYYY-MM-DD)
            - is_public: Видна ли цель публично (булево значение)

            Опциональные поля:
            - description: Описание цели (текст, может быть null)

            Особенности:
            - is_completed устанавливается в false по умолчанию
            - Проверяется существование пользователя и категории
            """,
        request=GoalCreateSerializer,
        responses={
            201: OpenApiResponse(
                response=GoalSerializer,
                description='Created',
                examples=[
                    OpenApiExample(
                        name="Цель успешно создана",
                        summary="Стандартный ответ при успешном создании",
                        value={
                            "id": 45,
                            "user_id": 123,
                            "title": "Накопить 100000 рублей",
                            "description": "Накопления на отпуск",
                            "category_id": 5,
                            "target_value": "100000.000",
                            "deadline": "2024-12-31",
                            "is_completed": False,
                            "is_public": True,
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
        tags=['Цели']
    )
    def create(self, request, *args, **kwargs):
        if request.data['user'] != request.user.id and request.user.role != User.UserRole.ADMIN:
            raise PermissionDenied('Нельзя создать цель у другого пользователя')
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Получить информацию о цели",
        description="""
            Получение информации о цели

            Возвращает полную информацию о конкретной цели по её ID.

            Права доступа:
            - Требуется действительный токен
            - Владелец цели может видеть любую информацию о своей цели
            - Администратор может видеть информацию о любой цели
            - Обычные пользователи могут видеть только публичные цели

            Возвращаемые поля:
            - id: Идентификатор цели
            - user_id: ID пользователя-владельца
            - title: Название цели
            - description: Описание цели
            - category_id: ID категории
            - target_value: Целевое значение
            - deadline: Дата завершения цели
            - is_completed: Завершена ли цель
            - is_public: Видна ли цель публично
            - created_at: Дата создания
            - updated_at: Дата обновления
            """,
        responses={
            200: OpenApiResponse(
                response=GoalSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Публичная цель",
                        summary="Информация о публичной цели",
                        value={
                            "id": 1,
                            "user_id": 123,
                            "title": "Прочитать 10 книг",
                            "description": "Литература для саморазвития",
                            "category_id": 2,
                            "target_value": "10.000",
                            "deadline": "2024-12-31",
                            "is_completed": False,
                            "is_public": True,
                            "created_at": "2024-01-10T09:15:30Z",
                            "updated_at": "2024-01-15T14:20:45Z"
                        }
                    ),
                    OpenApiExample(
                        name="Приватная цель",
                        summary="Информация о приватной цели (только для владельца/админа)",
                        value={
                            "id": 2,
                            "user_id": 123,
                            "title": "Личные финансовые цели",
                            "description": "Инвестиции и сбережения",
                            "category_id": 4,
                            "target_value": "500000.000",
                            "deadline": "2025-12-31",
                            "is_completed": False,
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
        tags=['Цели']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Обновить информацию о цели",
        description="""
            Полное обновление информации о цели

            Заменяет все данные цели новыми значениями. Все поля обязательны.

            Права доступа:
            - Требуется действительный токен
            - Владелец цели может обновлять только свою цель
            - Администратор может обновлять любую цель

            Обязательные поля:
            - title: Название цели
            - description: Описание цели (может быть null)
            - target_value: Целевое значение
            - deadline: Дата завершения цели
            - is_completed: Достигнута ли цель
            - is_public: Видна ли цель публично

            Валидация:
            - Проверка обязательных полей
            - Проверка типов данных
            - Проверка прав доступа

            Особенности:
            - Поле user_id обновить нельзя
            - Поле category_id обновить нельзя
            """,
        request=GoalUpdateSerializer,
        responses={
            200: OpenApiResponse(
                response=GoalSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Цель успешно обновлена",
                        summary="Стандартный ответ при успешном обновлении",
                        value={
                            "id": 1,
                            "user_id": 123,
                            "title": "Обновленное название",
                            "description": "Обновленное описание цели",
                            "category_id": 2,
                            "target_value": "15.000",
                            "deadline": "2024-09-30",
                            "is_completed": False,
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
        tags=['Цели']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Частично обновить информацию о цели",
        description="""
            Частичное обновление информации о цели

            Обновляет только указанные поля цели. Не указанные поля остаются без изменений.

            Права доступа:
            - Требуется действительный токен
            - Владелец цели может обновлять только свою цель
            - Администратор может обновлять любую цель

            Доступные для обновления поля:
            - title: Название цели
            - description: Описание цели (можно установить в null)
            - target_value: Целевое значение
            - deadline: Дата завершения цели
            - is_completed: Достигнута ли цель
            - is_public: Видна ли цель публично

            Особенности:
            - Можно обновлять любое подмножество полей
            - Не требуется передавать все поля
            - Нельзя изменить user_id, category_id
            """,
        request=GoalPartialUpdateSerializer,
        responses={
            200: OpenApiResponse(
                response=GoalSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Обновлено только описание",
                        summary="Обновлено одно поле",
                        value={
                            "id": 1,
                            "user_id": 123,
                            "title": "Похудение на 5 кг",
                            "description": "Новое подробное описание",
                            "category_id": 3,
                            "target_value": "5.000",
                            "deadline": "2024-06-30",
                            "is_completed": False,
                            "is_public": True,
                            "created_at": "2024-01-10T09:15:30Z",
                            "updated_at": "2024-01-15T15:45:00Z"
                        }
                    ),
                    OpenApiExample(
                        name="Обновлено несколько полей",
                        summary="Обновлены target_value и deadline",
                        value={
                            "id": 2,
                            "user_id": 123,
                            "title": "Накопить 100000 рублей",
                            "description": "Старое описание",
                            "category_id": 5,
                            "target_value": "150000.000",
                            "deadline": "2024-09-30",
                            "is_completed": False,
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
        tags=['Цели']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Удалить цель",
        description="""
            Удаление цели

            Полностью удаляет цель и все связанные записи прогресса из системы.

            Права доступа:
            - Требуется действительный токен
            - Владелец цели может удалить только свою цель
            - Администратор может удалить любую цель

            Последствия удаления:
            - Безвозвратное удаление цели
            - Каскадное удаление всех связанных записей прогресса
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
        tags=['Цели']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Получить цели пользователя",
        description="""
            Получение целей пользователя

            Получить список всех целей конкретного пользователя по его ID.

            Права доступа:
            - Требуется действительный токен
            - Пользователь может просматривать свои цели (все)
            - Администратор может просматривать цели любого пользователя (все)
            - Обычные пользователи могут просматривать только публичные цели других пользователей

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            """,
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID пользователя, чьи цели запрашиваются'
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
                response=GoalSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Список целей пользователя",
                        summary="Стандартный ответ со списком целей",
                        value={
                            "count": 8,
                            "next": None,
                            "previous": None,
                            "results": [
                                {
                                    "id": 1,
                                    "user_id": 123,
                                    "title": "Похудение на 5 кг",
                                    "description": "Снижение веса до 70 кг",
                                    "category_id": 3,
                                    "target_value": "5.000",
                                    "deadline": "2024-06-30",
                                    "is_completed": False,
                                    "is_public": True,
                                    "created_at": "2024-01-10T09:15:30Z",
                                    "updated_at": "2024-01-15T14:20:45Z"
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name="Пустой список целей",
                        summary="Когда у пользователя нет целей",
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
        tags=['Цели']
    )
    @action(detail=False, methods=['get'], url_path='user/(?P<user_id>[^/.]+)')
    def user_goals(self, request, user_id=None):
        user = get_object_or_404(User, id=user_id)

        current_user = request.user

        if current_user.id == user.id or current_user.role == User.UserRole.ADMIN:
            goals = Goal.objects.filter(user=user)
        else:
            goals = Goal.objects.filter(user=user, is_public=True)

        page = self.paginate_queryset(goals)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(goals, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Получить цели по категории",
        description="""
            Получение целей по категории

            Получить список всех целей с конкретной категорией по её ID.

            Права доступа:
            - Требуется действительный токен
            - Администратор может просматривать все цели категории
            - Обычные пользователи могут просматривать только публичные цели категории

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            """,
        parameters=[
            OpenApiParameter(
                name='category_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID категории, по которой запрашиваются цели'
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
                response=GoalSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Список целей категории",
                        summary="Стандартный ответ со списком целей",
                        value={
                            "count": 15,
                            "next": "http://127.0.0.1:8080/api/goals/category/3/?limit=10&offset=10",
                            "previous": None,
                            "results": [
                                {
                                    "id": 3,
                                    "user_id": 456,
                                    "title": "Выучить английский язык",
                                    "description": "Уровень B2 к концу года",
                                    "category_id": 3,
                                    "target_value": "1.000",
                                    "deadline": "2024-12-31",
                                    "is_completed": False,
                                    "is_public": True,
                                    "created_at": "2024-01-12T11:45:20Z",
                                    "updated_at": "2024-01-15T16:30:00Z"
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name="Пустой список целей",
                        summary="Когда в категории нет целей",
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
        tags=['Цели']
    )
    @action(detail=False, methods=['get'], url_path='category/(?P<category_id>[^/.]+)')
    def category_goals(self, request, category_id=None):
        category = get_object_or_404(Category, id=category_id)

        current_user = request.user

        if current_user.role == User.UserRole.ADMIN:
            goals = Goal.objects.filter(category=category)
        else:
            goals = Goal.objects.filter(category=category, is_public=True)

        page = self.paginate_queryset(goals)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(goals, many=True)
        return Response(serializer.data)


class GoalProgressViewSet(viewsets.ModelViewSet):
    queryset = GoalProgress.objects.all()
    pagination_class = GoalLimitOffsetPagination
    authentication_classes = [TokenAuthentication]

    def get_permissions(self):
        if self.action in ['retrieve', 'goal_progresses']:
            return [HasValidToken()]

        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [HasValidToken(), IsAdminOrSelf()]
        elif self.action in ['list']:
            return [IsAdmin()]

        return [HasValidToken()]

    def get_serializer_class(self):
        return {
            'create': GoalProgressCreateSerializer,
            'update': GoalProgressUpdateSerializer,
            'partial_update': GoalProgressPartialUpdateSerializer,
        }.get(self.action, GoalProgressSerializer)

    @extend_schema(
        summary="Список состояний прогресса",
        description="""
            Получение списка состояний прогресса

            Получить список всех состояний прогресса по всем целям всех пользователей.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут просматривать все состояния прогресса

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
                response=GoalProgressSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Список состояний прогресса",
                        summary="Стандартный ответ со списком состояний прогресса",
                        value={
                            "count": 150,
                            "next": "http://127.0.0.1:8080/api/goal-progress/?limit=10&offset=10",
                            "previous": None,
                            "results": [
                                {
                                    "id": 1,
                                    "goal": 5,
                                    "progress_date": "2024-01-15",
                                    "current_value": "2.500",
                                    "notes": "Прогресс хороший",
                                    "created_at": "2024-01-15T09:30:00Z",
                                    "updated_at": "2024-01-15T09:30:00Z"
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name="Пустой список состояний прогресса",
                        summary="Когда состояний прогресса нет",
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
        tags=['Прогресс по цели']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Создать новое состояние прогресса",
        description="""
            Создание нового состояния прогресса по цели

            Создает новую запись прогресса по цели.

            Права доступа:
            - Требуется действительный токен
            - Пользователь может создать прогресс только для своих целей
            - Администратор может создать прогресс для любой цели

            Ограничения:
            - Нельзя создать прогресс для уже завершенной цели
            - Нельзя создать прогресс после дедлайна цели

            Обязательные поля:
            - goal: ID цели
            - progress_date: Дата прогресса (в формате YYYY-MM-DD)
            - current_value: Текущее значение (число с точностью до 3 знаков после запятой)

            Опциональные поля:
            - notes: Примечания к прогрессу (текст, может быть null)

            Особенности:
            - Проверяется существование цели
            - Проверяется, что цель не завершена
            - Проверяется, что дата прогресса не позже дедлайна цели
            """,
        request=GoalProgressCreateSerializer,
        responses={
            201: OpenApiResponse(
                response=GoalProgressSerializer,
                description='Created',
                examples=[
                    OpenApiExample(
                        name="Прогресс успешно создан",
                        summary="Стандартный ответ при успешном создании",
                        value={
                            "id": 45,
                            "goal": 3,
                            "progress_date": "2024-01-15",
                            "current_value": "3.500",
                            "notes": "Хороший прогресс",
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
        tags=['Прогресс по цели']
    )
    def create(self, request, *args, **kwargs):
        goal = Goal.objects.filter(id=request.data['goal']).first()
        if goal.user != request.user and request.user.role != User.UserRole.ADMIN:
            raise PermissionDenied('Нельзя создать прогресс по цели у другого пользователя')
        if goal.is_completed:
            raise ValidationError({'detail': 'Нельзя создать прогресс по достигнутой цели'})
        if timezone.now().date() > goal.deadline:
            raise ValidationError({'detail': 'Нельзя создать прогресс после дедлайна'})
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Получить состояние прогресса",
        description="""
            Получение информации о состоянии прогресса

            Возвращает полную информацию о конкретном состоянии прогресса по его ID.

            Права доступа:
            - Требуется действительный токен
            - Владелец цели может видеть прогресс своей цели
            - Администратор может видеть любой прогресс
            - Обычные пользователи могут видеть прогресс публичных целей

            Возвращаемые поля:
            - id: Идентификатор прогресса
            - goal: ID цели
            - progress_date: Дата прогресса
            - current_value: Текущее значение
            - notes: Примечания
            - created_at: Дата создания записи прогресса
            - updated_at: Дата обновления записи прогресса

            """,
        responses={
            200: OpenApiResponse(
                response=GoalProgressSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Состояние прогресса",
                        summary="Информация о состоянии прогресса",
                        value={
                            "id": 1,
                            "goal": 3,
                            "progress_date": "2024-01-15",
                            "current_value": "3.500",
                            "notes": "Прогресс хороший",
                            "created_at": "2024-01-15T09:30:00Z",
                            "updated_at": "2024-01-15T09:30:00Z"
                        }
                    ),
                    OpenApiExample(
                        name="Прогресс без примечаний",
                        summary="Прогресс без notes",
                        value={
                            "id": 2,
                            "goal": 3,
                            "progress_date": "2024-01-14",
                            "current_value": "2.800",
                            "notes": None,
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
        tags=['Прогресс по цели']
    )
    def retrieve(self, request, *args, **kwargs):
        goal = Goal.objects.filter(id=request.data['goal']).first()
        if goal.user != request.user and not goal.is_public and request.user.role != User.UserRole.ADMIN:
            raise PermissionDenied('Нельзя получить прогресс приватной цели у другого пользователя')
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Обновить состояние прогресса",
        description="""
            Полное обновление информации о состоянии прогресса

            Заменяет все данные записи прогресса новыми значениями. Все поля обязательны.

            Права доступа:
            - Требуется действительный токен
            - Владелец цели может обновлять только прогресс своей цели
            - Администратор может обновлять любой прогресс

            Обязательные поля:
            - progress_date: Дата прогресса (в формате YYYY-MM-DD)
            - current_value: Текущее значение
            - notes: Примечания (может быть null)

            Валидация:
            - Проверка обязательных полей
            - Проверка формата даты
            - Проверка числового формата current_value
            - Проверка прав доступа

            Особенности:
            - Поле goal обновить нельзя
            """,
        request=GoalProgressUpdateSerializer,
        responses={
            200: OpenApiResponse(
                response=GoalProgressSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Прогресс успешно обновлен",
                        summary="Стандартный ответ при успешном обновлении",
                        value={
                            "id": 1,
                            "goal": 3,
                            "progress_date": "2024-01-16",
                            "current_value": "4.200",
                            "notes": "Обновленные примечания",
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
        tags=['Прогресс по цели']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Частично обновить состояние прогресса",
        description="""
            Частичное обновление информации о состоянии прогресса

            Обновляет только указанные поля записи прогресса. Не указанные поля остаются без изменений.

            Права доступа:
            - Требуется действительный токен
            - Владелец цели может обновлять только прогресс своей цели
            - Администратор может обновлять любой прогресс

            Доступные для обновления поля:
            - progress_date: Дата прогресса (в формате YYYY-MM-DD)
            - current_value: Текущее значение
            - notes: Примечания (можно установить в null)

            Особенности:
            - Можно обновлять любое подмножество полей
            - Не требуется передавать все поля
            - Нельзя изменить goal
            """,
        request=GoalProgressPartialUpdateSerializer,
        responses={
            200: OpenApiResponse(
                response=GoalProgressSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Обновлено только current_value",
                        summary="Обновлено одно поле",
                        value={
                            "id": 1,
                            "goal": 3,
                            "progress_date": "2024-01-15",
                            "current_value": "3.800",
                            "notes": "Прогресс хороший",
                            "created_at": "2024-01-15T09:30:00Z",
                            "updated_at": "2024-01-15T15:45:00Z"
                        }
                    ),
                    OpenApiExample(
                        name="Обновлены дата и примечания",
                        summary="Обновлено несколько полей",
                        value={
                            "id": 2,
                            "goal": 3,
                            "progress_date": "2024-01-14",
                            "current_value": "2.800",
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
        tags=['Прогресс по цели']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Удалить состояние прогресса",
        description="""
            Удаление состояния прогресса

            Полностью удаляет запись прогресса по цели из системы.

            Права доступа:
            - Требуется действительный токен
            - Владелец цели может удалить только прогресс своей цели
            - Администратор может удалить любой прогресс

            Последствия удаления:
            - Безвозвратное удаление записи прогресса
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
        tags=['Прогресс по цели']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Получить состояния прогресса по цели",
        description="""
            Получение состояний прогресса по цели

            Получить список всех состояний прогресса конкретной цели по её ID.

            Права доступа:
            - Требуется действительный токен
            - Владелец цели может просматривать все состояния прогресса своей цели
            - Администратор может просматривать состояния прогресса любой цели
            - Обычные пользователи не могут просматривать прогресс чужих целей

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            """,
        parameters=[
            OpenApiParameter(
                name='goal_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID цели, чьи состояния прогресса запрашиваются'
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
                response=GoalProgressSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Список состояний прогресса цели",
                        summary="Стандартный ответ со списком состояний прогресса",
                        value={
                            "count": 8,
                            "next": None,
                            "previous": None,
                            "results": [
                                {
                                    "id": 15,
                                    "goal": 3,
                                    "progress_date": "2024-01-15",
                                    "current_value": "3.500",
                                    "notes": "Прогресс хороший",
                                    "created_at": "2024-01-15T09:30:00Z",
                                    "updated_at": "2024-01-15T09:30:00Z"
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name="Пустой список состояний прогресса",
                        summary="Когда у цели нет состояний прогресса",
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
        tags=['Прогресс по цели']
    )
    @action(detail=False, methods=['get'], url_path='goal/(?P<goal_id>[^/.]+)')
    def goal_progresses(self, request, goal_id=None):
        goal = get_object_or_404(Goal, id=goal_id)

        current_user = request.user

        if current_user == goal.user or current_user.role == User.UserRole.ADMIN:
            goals_progresses = GoalProgress.objects.filter(goal=goal)
        else:
            raise PermissionDenied('Нет доступа к приватным целям')

        page = self.paginate_queryset(goals_progresses)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(goals_progresses, many=True)
        return Response(serializer.data)


class BatchGoalCreateView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken, IsAdmin]

    @extend_schema(
        summary="Батчевая загрузка целей",
        description="""
            Массовое создание целей

            Создание нескольких целей за одну операцию с использованием bulk_create.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут создавать цели батчами

            Обязательные поля для каждой цели:
            - user_id: ID пользователя-владельца
            - title: Название цели (строка, максимум 255 символов)
            - category_id: ID категории
            - target_value: Целевое значение (число с точностью до 3 знаков после запятой)
            - deadline: Дата завершения цели (в формате YYYY-MM-DD)

            Опциональные поля:
            - description: Описание цели (текст, может быть null)
            - is_completed: Завершена ли цель (по умолчанию: false)
            - is_public: Видна ли цель публично (по умолчанию: true)

            Ограничения:
            - Максимум 10,000 целей за запрос
            - batch_size от 1 до 5,000
            - user_id и category_id должны существовать
            - title должен быть уникальным для каждого пользователя
            - target_value должно быть числом с точностью до 3 знаков после запятой
            """,
        request=BatchGoalCreateSerializer,
        responses={
            200: OpenApiResponse(
                response=BatchOperationLogSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Полностью успешная операция",
                        summary="Все цели созданы",
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
                        summary="Некоторые цели не созданы",
                        value={
                            "total_processed": 5,
                            "successful": 3,
                            "failed": 2,
                            "batch_size": 100,
                            "errors": [
                                {
                                    "data": {
                                        "user_id": 123,
                                        "title": "Похудение на 5 кг",
                                        "category_id": 3,
                                        "target_value": "5.000",
                                        "deadline": "2024-06-30"
                                    },
                                    "error": "Цель с title 'Похудение на 5 кг' для пользователя 123 уже существует",
                                    "type": "duplicate_error"
                                },
                                {
                                    "data": {
                                        "user_id": 999,
                                        "title": "Накопить 100000 рублей",
                                        "category_id": 5,
                                        "target_value": "100000.000",
                                        "deadline": "2024-12-31"
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
        tags=['Цели']
    )
    def post(self, request):
        serializer = BatchGoalCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Ошибка валидации',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        goals_data = serializer.validated_data['goals']
        batch_size = serializer.validated_data['batch_size']

        operation_log = {
            'total_processed': len(goals_data),
            'successful': 0,
            'failed': 0,
            'errors': [],
            'created_ids': [],
            'batches_processed': 0,
            'batch_size': batch_size
        }

        try:
            validated_goals_data = []
            seen_combinations = set()

            user_ids = User.objects.values_list('id', flat=True)
            category_ids = Category.objects.values_list('id', flat=True)

            for i, goal_data in enumerate(goals_data):
                try:
                    processed_data = goal_data.copy()

                    required_fields = ['user_id', 'title', 'target_value', 'deadline', 'category_id']
                    missing_fields = []

                    for field in required_fields:
                        if field not in processed_data:
                            missing_fields.append(field)

                    if missing_fields:
                        raise ValueError(f"Обязательные поля отсутствуют: {', '.join(missing_fields)}")

                    user_id = processed_data['user_id']
                    title = processed_data['title']
                    target_value = processed_data['target_value']
                    deadline = processed_data['deadline']
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

                    combination = f"{processed_data['user_id']}:{title}"
                    if combination in seen_combinations:
                        raise ValueError(
                            f"Цель с title '{title}' для пользователя {user_id} дублируется в запросе")
                    seen_combinations.add(combination)

                    if processed_data['user_id'] not in user_ids:
                        raise ValueError(f"Пользователь с ID {processed_data['user_id']} не существует")

                    if processed_data['category_id'] not in category_ids:
                        raise ValueError(f"Категория с ID {category_id} не существует")

                    try:
                        target_value_decimal = Decimal(str(target_value))
                        processed_data['target_value'] = target_value_decimal.quantize(Decimal('0.001'))
                    except (ValueError, TypeError, InvalidOperation):
                        raise ValueError(
                            f"target_value должно быть числом (до 3 знаков после запятой), получено: {target_value}")

                    if isinstance(deadline, str):
                        try:
                            processed_data['deadline'] = datetime.strptime(deadline, '%Y-%m-%d').date()
                        except ValueError:
                            raise ValueError(f"deadline должен быть в формате YYYY-MM-DD, получено: {deadline}")
                    elif not isinstance(deadline, date):
                        raise ValueError(f"deadline должен быть датой, получено: {deadline}")

                    if 'is_completed' in processed_data:
                        is_completed = processed_data['is_completed']
                        if not isinstance(is_completed, bool):
                            raise ValueError(f"is_completed должен быть булевым значением, получено: {is_completed}")
                    else:
                        processed_data['is_completed'] = False

                    if 'is_public' in processed_data:
                        is_public = processed_data['is_public']
                        if not isinstance(is_public, bool):
                            raise ValueError(f"is_public должен быть булевым значением, получено: {is_public}")
                    else:
                        processed_data['is_public'] = True

                    if 'description' in processed_data and processed_data['description'] is not None:
                        if not isinstance(processed_data['description'], str):
                            raise ValueError(
                                f"description должен быть строкой, получено: {processed_data['description']}")

                    validated_goals_data.append({
                        'index': i,
                        'data': processed_data,
                        'user_id': processed_data['user_id'],
                        'title': title
                    })

                except serializers.ValidationError as e:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': goal_data,
                        'error': e.detail,
                        'type': 'validation_error'
                    })
                except Exception as e:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': goal_data,
                        'error': str(e),
                        'type': 'validation_error'
                    })

            if not validated_goals_data:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            goal_identifiers = []
            for item in validated_goals_data:
                goal_identifiers.append({
                    'user_id': item['user_id'],
                    'title': item['title']
                })

            existing_goals = {}
            if goal_identifiers:
                q_objects = Q()
                for identifier in goal_identifiers:
                    q_objects |= Q(
                        user_id=identifier['user_id'],
                        title=identifier['title']
                    )

                existing_qs = Goal.objects.filter(q_objects)
                for goal in existing_qs:
                    key = f"{goal.user_id}:{goal.title}"
                    existing_goals[key] = goal

            filtered_goals = []

            for item in validated_goals_data:
                user_id = item['user_id']
                title = item['title']
                key = f"{user_id}:{title}"

                if key in existing_goals:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': item['data'],
                        'error': f'Цель с title "{title}" для пользователя {user_id} уже существует',
                        'type': 'duplicate_error'
                    })
                else:
                    filtered_goals.append(item)

            if not filtered_goals:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            user_ids = set()
            category_ids = set()

            for item in filtered_goals:
                data = item['data']
                user_ids.add(data['user_id'])
                category_ids.add(data['category_id'])

            users_dict = {user.id: user for user in User.objects.filter(id__in=user_ids)}
            categories_dict = {cat.id: cat for cat in Category.objects.filter(id__in=category_ids)}

            missing_users = user_ids - set(users_dict.keys())
            if missing_users:
                for item in filtered_goals:
                    if item['data']['user_id'] in missing_users:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'data': item['data'],
                            'error': f'Пользователь с ID {item["data"]["user_id"]} не существует',
                            'type': 'reference_error'
                        })
                filtered_goals = [
                    item for item in filtered_goals
                    if item['data']['user_id'] not in missing_users
                ]

            missing_categories = category_ids - set(categories_dict.keys())
            if missing_categories:
                for item in filtered_goals:
                    if item['data']['category_id'] in missing_categories:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'data': item['data'],
                            'error': f'Категория с ID {item["data"]["category_id"]} не существует',
                            'type': 'reference_error'
                        })
                filtered_goals = [
                    item for item in filtered_goals
                    if item['data']['category_id'] not in missing_categories
                ]

            if not filtered_goals:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            batches = [
                filtered_goals[i:i + batch_size]
                for i in range(0, len(filtered_goals), batch_size)
            ]

            for batch_index, batch in enumerate(batches):
                goals_to_create = []

                for item in batch:
                    goal_data = dict(item['data'])

                    try:
                        user = users_dict[goal_data['user_id']]
                        category = categories_dict[goal_data['category_id']]

                        goal = Goal(
                            user=user,
                            title=goal_data['title'],
                            description=goal_data.get('description'),
                            category=category,
                            target_value=goal_data['target_value'],
                            deadline=goal_data['deadline'],
                            is_completed=goal_data['is_completed'],
                            is_public=goal_data['is_public'],
                            created_at=timezone.now(),
                            updated_at=timezone.now()
                        )

                        goals_to_create.append(goal)
                    except KeyError as e:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'data': goal_data,
                            'error': f'Ошибка при создании цели: {str(e)}',
                            'type': 'creation_error'
                        })
                    except Exception as e:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'data': goal_data,
                            'error': f'Ошибка при создании цели: {str(e)}',
                            'type': 'creation_error'
                        })

                with connection.cursor() as cursor:
                    cursor.execute("ALTER TABLE goals DISABLE TRIGGER audit_goals_trigger")

                try:
                    with transaction.atomic():
                        if goals_to_create:
                            try:
                                created = Goal.objects.bulk_create(
                                    goals_to_create,
                                    batch_size=len(goals_to_create)
                                )
                                operation_log['successful'] += len(created)

                                if created:
                                    created_ids = [goal.id for goal in created]
                                    operation_log['created_ids'].extend(created_ids)

                            except IntegrityError as e:
                                operation_log['failed'] += len(goals_to_create)
                                operation_log['errors'].append({
                                    'type': 'integrity_error',
                                    'error': 'Ошибка целостности при bulk_create',
                                    'details': str(e)
                                })
                                raise
                            except Exception as e:
                                operation_log['failed'] += len(goals_to_create)
                                operation_log['errors'].append({
                                    'type': 'bulk_create_error',
                                    'error': str(e)
                                })

                finally:
                    with connection.cursor() as cursor:
                        cursor.execute("ALTER TABLE goals ENABLE TRIGGER audit_goals_trigger")

                operation_log['batches_processed'] += 1

        except Exception as e:
            operation_log['errors'].append({
                'type': 'critical',
                'error': str(e)
            })
            operation_log['failed'] = operation_log['total_processed'] - operation_log['successful']

        batch_log = BatchLog(
            table_name='goals',
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


class BatchGoalProgressCreateView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken, IsAdmin]

    @extend_schema(
        summary="Батчевая загрузка прогресса по целям",
        description="""
            Массовое создание прогресса по целям

            Создание нескольких записей прогресса по целям за одну операцию с использованием bulk_create.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут создавать прогресс по целям батчами

            Обязательные поля для каждой записи прогресса:
            - goal_id: ID цели
            - progress_date: Дата прогресса (в формате YYYY-MM-DD)
            - current_value: Текущее значение (число с точностью до 3 знаков после запятой)

            Опциональные поля:
            - notes: Примечания к прогрессу (текст, может быть null)

            Ограничения:
            - Максимум 10,000 записей прогресса за запрос
            - batch_size от 1 до 5,000
            - goal_id должен существовать
            - progress_date должен быть в правильном формате
            - current_value должно быть числом с точностью до 3 знаков после запятой
            """,
        request=BatchGoalProgressCreateSerializer,
        responses={
            200: OpenApiResponse(
                response=BatchOperationLogSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Полностью успешная операция",
                        summary="Все записи прогресса созданы",
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
                        summary="Некоторые записи прогресса не созданы",
                        value={
                            "total_processed": 5,
                            "successful": 3,
                            "failed": 2,
                            "batch_size": 100,
                            "errors": [
                                {
                                    "data": {
                                        "goal_id": 3,
                                        "progress_date": "2024-01-15",
                                        "current_value": "2.500"
                                    },
                                    "error": "Цель с ID 3 не существует",
                                    "type": "reference_error"
                                },
                                {
                                    "data": {
                                        "goal_id": 5,
                                        "progress_date": "неправильная дата",
                                        "current_value": "1.500"
                                    },
                                    "error": "progress_date должен быть в формате YYYY-MM-DD, получено:"
                                             " неправильная дата",
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
        tags=['Прогресс по цели']
    )
    def post(self, request):
        serializer = BatchGoalProgressCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Ошибка валидации',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        goal_progresses_data = serializer.validated_data['goal_progresses']
        batch_size = serializer.validated_data['batch_size']

        operation_log = {
            'total_processed': len(goal_progresses_data),
            'successful': 0,
            'failed': 0,
            'errors': [],
            'created_ids': [],
            'batches_processed': 0,
            'batch_size': batch_size
        }

        try:
            validated_goal_progresses_data = []

            goal_ids = Goal.objects.values_list('id', flat=True)

            for i, goal_progress_data in enumerate(goal_progresses_data):
                try:
                    processed_data = goal_progress_data.copy()

                    required_fields = ['goal_id', 'progress_date', 'current_value']
                    missing_fields = []

                    for field in required_fields:
                        if field not in processed_data:
                            missing_fields.append(field)

                    if missing_fields:
                        raise ValueError(f"Обязательные поля отсутствуют: {', '.join(missing_fields)}")

                    goal_id = processed_data['goal_id']
                    progress_date = processed_data['progress_date']
                    current_value = processed_data['current_value']

                    if isinstance(goal_id, str):
                        try:
                            processed_data['goal_id'] = int(goal_id)
                        except ValueError:
                            raise ValueError(f"goal_id должен быть целым числом, получено: {goal_id}")
                    elif not isinstance(goal_id, int):
                        raise ValueError(f"goal_id должен быть целым числом, получено: {goal_id}")

                    try:
                        current_value_decimal = Decimal(str(current_value))
                        processed_data['current_value'] = current_value_decimal.quantize(Decimal('0.001'))
                    except (ValueError, TypeError, InvalidOperation):
                        raise ValueError(
                            f"current_value должно быть числом (до 3 знаков после запятой), получено: {current_value}")

                    if isinstance(progress_date, str):
                        try:
                            processed_data['progress_date'] = datetime.strptime(progress_date, '%Y-%m-%d').date()
                        except ValueError:
                            raise ValueError(f"progress_date должен быть в формате YYYY-MM-DD, получено: {progress_date}")
                    elif not isinstance(progress_date, date):
                        raise ValueError(f"progress_date должен быть датой, получено: {progress_date}")

                    if processed_data['goal_id'] not in goal_ids:
                        raise ValueError(f"Цель с ID {processed_data['goal_id']} не существует")

                    if 'notes' in processed_data and processed_data['notes'] is not None:
                        if not isinstance(processed_data['notes'], str):
                            raise ValueError(
                                f"notes должен быть строкой, получено: {processed_data['notes']}")

                    validated_goal_progresses_data.append({
                        'index': i,
                        'data': processed_data,
                        'goal_id': processed_data['goal_id'],
                        'progress_date': processed_data['progress_date']
                    })

                except serializers.ValidationError as e:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': goal_progress_data,
                        'error': e.detail,
                        'type': 'validation_error'
                    })
                except Exception as e:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': goal_progress_data,
                        'error': str(e),
                        'type': 'validation_error'
                    })

            if not validated_goal_progresses_data:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            goal_ids_set = set()

            for item in validated_goal_progresses_data:
                data = item['data']
                goal_ids_set.add(data['goal_id'])

            goals_dict = {goal.id: goal for goal in Goal.objects.filter(id__in=goal_ids_set)}

            missing_goals = goal_ids_set - set(goals_dict.keys())
            if missing_goals:
                for item in validated_goal_progresses_data:
                    if item['data']['goal_id'] in missing_goals:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'data': item['data'],
                            'error': f'Цель с ID {item["data"]["goal_id"]} не существует',
                            'type': 'reference_error'
                        })
                validated_goal_progresses_data = [
                    item for item in validated_goal_progresses_data
                    if item['data']['goal_id'] not in missing_goals
                ]

            if not validated_goal_progresses_data:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            batches = [
                validated_goal_progresses_data[i:i + batch_size]
                for i in range(0, len(validated_goal_progresses_data), batch_size)
            ]

            for batch_index, batch in enumerate(batches):
                goal_progresses_to_create = []

                for item in batch:
                    goal_progress_data = item['data']

                    try:
                        goal = goals_dict[goal_progress_data['goal_id']]

                        goal_progress = GoalProgress(
                            goal=goal,
                            progress_date=goal_progress_data['progress_date'],
                            current_value=goal_progress_data['current_value'],
                            notes=goal_progress_data.get('notes'),
                            created_at=timezone.now(),
                            updated_at=timezone.now()
                        )

                        goal_progresses_to_create.append(goal_progress)
                    except KeyError as e:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'data': goal_progress_data,
                            'error': f'Ошибка при создании прогресса по цели: {str(e)}',
                            'type': 'creation_error'
                        })
                    except Exception as e:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'data': goal_progress_data,
                            'error': f'Ошибка при создании прогресса по цели: {str(e)}',
                            'type': 'creation_error'
                        })

                with connection.cursor() as cursor:
                    cursor.execute("ALTER TABLE goal_progresses DISABLE TRIGGER audit_goal_progresses_trigger")

                try:
                    with transaction.atomic():
                        if goal_progresses_to_create:
                            try:
                                created = GoalProgress.objects.bulk_create(
                                    goal_progresses_to_create,
                                    batch_size=len(goal_progresses_to_create)
                                )
                                operation_log['successful'] += len(created)

                                if created:
                                    created_ids = [goal_progress.id for goal_progress in created]
                                    operation_log['created_ids'].extend(created_ids)

                            except IntegrityError as e:
                                operation_log['failed'] += len(goal_progresses_to_create)
                                operation_log['errors'].append({
                                    'type': 'integrity_error',
                                    'error': 'Ошибка целостности при bulk_create',
                                    'details': str(e)
                                })
                                raise
                            except Exception as e:
                                operation_log['failed'] += len(goal_progresses_to_create)
                                operation_log['errors'].append({
                                    'type': 'bulk_create_error',
                                    'error': str(e)
                                })

                finally:
                    with connection.cursor() as cursor:
                        cursor.execute("ALTER TABLE goal_progresses ENABLE TRIGGER audit_goal_progresses_trigger")

                operation_log['batches_processed'] += 1

        except Exception as e:
            operation_log['errors'].append({
                'type': 'critical',
                'error': str(e)
            })
            operation_log['failed'] = operation_log['total_processed'] - operation_log['successful']

        batch_log = BatchLog(
            table_name='goal_progresses',
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
