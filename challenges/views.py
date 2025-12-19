from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.template.defaultfilters import date
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import connection, transaction, IntegrityError
from rest_framework.views import APIView

from audit.models import BatchLog
from bdcw.authentication import TokenAuthentication, HasValidToken, IsAdmin
from bdcw.error_responses import (BAD_REQUEST_RESPONSE, UNAUTHORIZED_RESPONSE, FORBIDDEN_RESPONSE, NOT_FOUND_RESPONSE,
                                  INTERNAL_SERVER_ERROR, BAD_BATCH_REQUEST_RESPONSE)
from categories.models import Category
from categories.serializers import CategorySerializer
from core.serializers import UserSerializer, BatchOperationLogSerializer
from goals.models import Goal
from goals.serializers import GoalSerializer
from .models import Challenge, GoalChallenge, ChallengeCategory
from core.models import User
from .serializers import ChallengeSerializer, ChallengeCreateAndUpdateSerializer, ChallengePartialUpdateSerializer, \
    AppendCategoryToChallengeSerializer, AppendGoalToChallengeSerializer, GoalChallengeSerializer, \
    GoalLeaderboardSerializer, UserLeaderboardSerializer, BatchChallengeCreateSerializer
from rest_framework.pagination import LimitOffsetPagination


class ChallengeLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 10
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 100


class ChallengeViewSet(viewsets.ModelViewSet):
    queryset = Challenge.objects.all()
    pagination_class = ChallengeLimitOffsetPagination
    authentication_classes = [TokenAuthentication]

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'challenge_categories', 'category_challenges', 'challenge_users',
                           'challenge_goals', 'goal_challenges', 'user_challenges', 'user_leaderboard',
                           'goal_leaderboard']:
            return [HasValidToken()]

        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [HasValidToken(), IsAdmin()]

        return [HasValidToken()]

    def get_serializer_class(self):
        return {
            'create': ChallengeCreateAndUpdateSerializer,
            'update': ChallengeCreateAndUpdateSerializer,
            'partial_update': ChallengePartialUpdateSerializer,
        }.get(self.action, ChallengeSerializer)

    @extend_schema(
        summary='олучить список челленджей',
        description='''
            Получение списка челленджей

            Возвращает список всех челленджей с пагинацией.

            Особенности:
            - Все пользователи видят все челленджи

            Права доступа:
            - Требуется действительный токен

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            ''',
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
                response=ChallengeSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Список челленджей',
                        summary='Стандартный ответ со списком челленджей',
                        value={
                            'count': 15,
                            'next': 'http://127.0.0.1:8080/api/challenges/?limit=10&offset=10',
                            'previous': None,
                            'results': [
                                {
                                    'id': 1,
                                    'name': 'Зимний фитнес-челлендж',
                                    'description': 'Тренировки всю зиму',
                                    'start_date': '2024-01-01',
                                    'end_date': '2024-03-31',
                                    'is_active': True,
                                    'created_at': '2024-01-10T09:15:30Z',
                                    'updated_at': '2024-01-15T14:20:45Z'
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name='Пустой список челленджей',
                        summary='Когда челленджей нет',
                        value={
                            'count': 0,
                            'next': None,
                            'previous': None,
                            'results': []
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Челленджи']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary='Создать челлендж',
        description='''
            Создание нового челленджа

            Создает новый челлендж для участия пользователей.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут создавать челленджи

            Обязательные поля:
            - name: Название челленджа (строка, максимум 255 символов)
            - start_date: Дата начала челленджа (в формате YYYY-MM-DD)
            - end_date: Дата окончания челленджа (в формате YYYY-MM-DD)
            - is_active: Активен ли челлендж (булево значение)

            Опциональные поля:
            - description: Описание челленджа (текст, может быть null)
            ''',
        request=ChallengeCreateAndUpdateSerializer,
        responses={
            201: OpenApiResponse(
                response=ChallengeSerializer,
                description='Created',
                examples=[
                    OpenApiExample(
                        name='Челлендж успешно создан',
                        summary='Стандартный ответ при успешном создании',
                        value={
                            'id': 45,
                            'name': 'Новогодний челлендж',
                            'description': 'Достижение целей к Новому году',
                            'start_date': '2024-11-01',
                            'end_date': '2024-12-31',
                            'is_active': True,
                            'created_at': '2024-01-15T10:30:00Z',
                            'updated_at': '2024-01-15T10:30:00Z'
                        }
                    )
                ]
            ),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Челленджи']
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary='Получить информацию о челлендже',
        description='''
            Получение информации о челлендже

            Возвращает полную информацию о конкретном челлендже по его ID.

            Права доступа:
            - Требуется действительный токен
            - Все пользователи могут видеть информацию о челленджах

            Возвращаемые поля:
            - id: Идентификатор челленджа
            - name: Название челленджа
            - description: Описание челленджа
            - start_date: Дата начала челленджа
            - end_date: Дата окончания челленджа
            - is_active: Активен ли челлендж
            - created_at: Дата создания
            - updated_at: Дата обновления
            ''',
        responses={
            200: OpenApiResponse(
                response=ChallengeSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Активный челлендж',
                        summary='Информация об активном челлендже',
                        value={
                            'id': 1,
                            'name': 'Летний беговой челлендж',
                            'description': 'Пробежать 100 км за лето',
                            'start_date': '2024-06-01',
                            'end_date': '2024-08-31',
                            'is_active': True,
                            'created_at': '2024-01-10T09:15:30Z',
                            'updated_at': '2024-01-15T14:20:45Z'
                        }
                    ),
                    OpenApiExample(
                        name='Неактивный челлендж',
                        summary='Информация о завершенном челлендже',
                        value={
                            'id': 2,
                            'name': 'Весенний челлендж',
                            'description': 'Челлендж прошлой весны',
                            'start_date': '2023-03-01',
                            'end_date': '2023-05-31',
                            'is_active': False,
                            'created_at': '2024-01-12T11:45:20Z',
                            'updated_at': '2024-01-15T16:30:00Z'
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Челленджи']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary='Обновить информацию о челлендже',
        description='''
            Полное обновление информации о челлендже

            Заменяет все данные челленджа новыми значениями. Все поля обязательны.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут обновлять челленджи

            Обязательные поля:
            - name: Название челленджа
            - description: Описание челленджа (может быть null)
            - start_date: Дата начала челленджа
            - end_date: Дата окончания челленджа
            - is_active: Активен ли челлендж

            Валидация:
            - Проверка обязательных полей
            - Проверка типов данных
            - Проверка прав доступа
            - Проверка, что end_date позже start_date
            ''',
        request=ChallengeCreateAndUpdateSerializer,
        responses={
            200: OpenApiResponse(
                response=ChallengeSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Челлендж успешно обновлен',
                        summary='Стандартный ответ при успешном обновлении',
                        value={
                            'id': 1,
                            'name': 'Обновленное название',
                            'description': 'Обновленное описание челленджа',
                            'start_date': '2024-02-01',
                            'end_date': '2024-04-30',
                            'is_active': True,
                            'created_at': '2024-01-10T09:15:30Z',
                            'updated_at': '2024-01-15T15:30:00Z'
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
        tags=['Челленджи']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary='Частично обновить информацию о челлендже',
        description='''
            Частичное обновление информации о челлендже

            Обновляет только указанные поля челленджа. Не указанные поля остаются без изменений.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут обновлять челленджи

            Доступные для обновления поля:
            - name: Название челленджа
            - description: Описание челленджа (можно установить в null)
            - start_date: Дата начала челленджа
            - end_date: Дата окончания челленджа
            - is_active: Активен ли челлендж

            Особенности:
            - Можно обновлять любое подмножество полей
            - Не требуется передавать все поля
            ''',
        request=ChallengePartialUpdateSerializer,
        responses={
            200: OpenApiResponse(
                response=ChallengeSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Обновлено только название',
                        summary='Обновлено одно поле',
                        value={
                            'id': 1,
                            'name': 'Новое название челленджа',
                            'description': 'Старое описание',
                            'start_date': '2024-06-01',
                            'end_date': '2024-08-31',
                            'is_active': True,
                            'created_at': '2024-01-10T09:15:30Z',
                            'updated_at': '2024-01-15T15:45:00Z'
                        }
                    ),
                    OpenApiExample(
                        name='Обновлены даты',
                        summary='Обновлено несколько полей',
                        value={
                            'id': 2,
                            'name': 'Весенний челлендж',
                            'description': 'Старое описание',
                            'start_date': '2024-03-01',
                            'end_date': '2024-05-31',
                            'is_active': False,
                            'created_at': '2024-01-12T11:45:20Z',
                            'updated_at': '2024-01-15T15:45:00Z'
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
        tags=['Челленджи']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary='Удалить челлендж',
        description='''
            Удаление челленджа

            Полностью удаляет челлендж и все связанные записи из системы.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут удалять челленджи

            Последствия удаления:
            - Безвозвратное удаление челленджа
            - Каскадное удаление всех связей с категориями
            - Каскадное удаление всех связей с целями
            ''',
        responses={
            204: OpenApiResponse(
                description='No Content'
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Челленджи']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary='Получить категории челленджа',
        description='''
            Получение категорий челленджа

            Получить список всех категорий данного челленджа по его ID.

            Права доступа:
            - Требуется действительный токен
            - Все пользователи могут просматривать категории челленджей

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            ''',
        parameters=[
            OpenApiParameter(
                name='challenge_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID челленджа, чьи категории запрашиваются'
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
                response=CategorySerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Список категорий челленджа',
                        summary='Стандартный ответ со списком категорий',
                        value={
                            'count': 3,
                            'next': None,
                            'previous': None,
                            'results': [
                                {
                                    'id': 1,
                                    'name': 'Фитнес',
                                    'description': 'Спортивные цели',
                                    'created_at': '2024-01-10T09:15:30Z',
                                    'updated_at': '2024-01-15T14:20:45Z'
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name='Пустой список категорий',
                        summary='Когда у челленджа нет категорий',
                        value={
                            'count': 0,
                            'next': None,
                            'previous': None,
                            'results': []
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Челленджи']
    )
    @action(detail=False, methods=['get'], url_path='categories_by_challenge/(?P<challenge_id>[^/.]+)')
    def challenge_categories(self, request, challenge_id=None):
        try:
            Challenge.objects.get(id=challenge_id)
        except Challenge.DoesNotExist:
            return Response(
                {'error': 'Челлендж не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        categories = Category.objects.raw('''
            SELECT c.id, c.name, c.description, c.created_at, c.updated_at 
            FROM categories c 
            JOIN challenge_categories cc ON c.id = cc.category_id 
            WHERE cc.challenge_id = %s''', (challenge_id,))

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(categories, request)

        if page is not None:
            serializer = CategorySerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary='Получить челленджи по категории',
        description='''
            Получение челленджей по категории

            Получить список всех челленджей с данной категорией по её ID.

            Права доступа:
            - Требуется действительный токен
            - Все пользователи могут просматривать челленджи по категории
            
            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            ''',
        parameters=[
            OpenApiParameter(
                name='category_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID категории, по которой запрашиваются челленджи'
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
                response=ChallengeSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Список челленджей категории',
                        summary='Стандартный ответ со списком челленджей',
                        value={
                            'count': 5,
                            'next': None,
                            'previous': None,
                            'results': [
                                {
                                    'id': 1,
                                    'name': 'Фитнес-челлендж',
                                    'description': 'Спортивные достижения',
                                    'start_date': '2024-01-01',
                                    'end_date': '2024-03-31',
                                    'is_active': True,
                                    'created_at': '2024-01-10T09:15:30Z',
                                    'updated_at': '2024-01-15T14:20:45Z'
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name='Пустой список челленджей',
                        summary='Когда в категории нет челленджей',
                        value={
                            'count': 0,
                            'next': None,
                            'previous': None,
                            'results': []
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Челленджи']
    )
    @action(detail=False, methods=['get'], url_path='challenges_by_category/(?P<category_id>[^/.]+)')
    def category_challenges(self, request, category_id=None):
        try:
            Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return Response(
                {'error': 'Категория не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

        challenges = Category.objects.raw('''
                SELECT c.id, c.name, c.description, c.target_value, 
                    c.start_date, c.end_date, c.is_active, c.created_at, c.updated_at 
                FROM challenges c
                JOIN challenge_categories cc ON c.id = cc.challenge_id
                WHERE cc.category_id = %s''', (category_id,))

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(challenges, request)

        if page is not None:
            serializer = ChallengeSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = ChallengeSerializer(challenges, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary='Получить участников челленджа',
        description='''
            Получение участников челленджа

            Получить список всех участников данного челленджа по его ID.

            Права доступа:
            - Требуется действительный токен
            - Все пользователи могут просматривать участников челленджей

            Особенности:
            - Возвращает список пользователей с пагинацией
            - Возвращаются только публичные пользователи
            - Учитываются только пользователи, чьи цели участвуют в челлендже

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            ''',
        parameters=[
            OpenApiParameter(
                name='challenge_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID челленджа, чьи участники запрашиваются'
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
                response=UserSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Список участников челленджа',
                        summary='Стандартный ответ со списком участников',
                        value={
                            'count': 8,
                            'next': None,
                            'previous': None,
                            'results': [
                                {
                                    'id': 123,
                                    'username': 'user123',
                                    'first_name': 'Иван',
                                    'last_name': 'Иванов',
                                    'description': 'Участник челленджа',
                                    'role': 'user',
                                    'is_active': True,
                                    'is_public': True,
                                    'created_at': '2024-01-10T09:15:30Z',
                                    'updated_at': '2024-01-15T14:20:45Z'
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name='Пустой список участников',
                        summary='Когда в челлендже нет участников',
                        value={
                            'count': 0,
                            'next': None,
                            'previous': None,
                            'results': []
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Челленджи']
    )
    @action(detail=False, methods=['get'], url_path='challenge_users/(?P<challenge_id>[^/.]+)')
    def challenge_users(self, request, challenge_id=None):
        try:
            Challenge.objects.get(id=challenge_id)
        except Challenge.DoesNotExist:
            return Response(
                {'error': 'Челлендж не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        users = User.objects.raw('''
                    SELECT DISTINCT u.id, u.username, u.first_name, u.last_name, u.description, u.role,
                           u.is_active, u.is_public, u.created_at, u.updated_at
                    FROM users u
                    JOIN goals g ON g.user_id = u.id
                    JOIN goal_challenges gc ON g.id = gc.goal_id 
                    WHERE gc.challenge_id = %s AND u.is_public = true''', (challenge_id,))

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(users, request)

        if page is not None:
            serializer = UserSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary='Получить цели челленджа',
        description='''
            Получение целей челленджа

            Получить список всех целей, участвующих в данном челлендже по его ID.

            Права доступа:
            - Требуется действительный токен
            - Все пользователи могут просматривать цели челленджей

            Особенности:
            - Возвращает список целей с пагинацией
            - Возвращаются только публичные цели
            - Учитываются только цели, участвующие в челлендже

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            ''',
        parameters=[
            OpenApiParameter(
                name='challenge_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID челленджа, чьи цели запрашиваются'
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
                        name='Список целей челленджа',
                        summary='Стандартный ответ со списком целей',
                        value={
                            'count': 12,
                            'next': 'http://127.0.0.1:8080/api/challenges/challenge_goals/1/?limit=10&offset=10',
                            'previous': None,
                            'results': [
                                {
                                    'id': 5,
                                    'user_id': 123,
                                    'title': 'Похудение на 5 кг',
                                    'description': 'Участвует в челлендже',
                                    'category_id': 3,
                                    'deadline': '2024-06-30',
                                    'is_completed': False,
                                    'is_public': True,
                                    'created_at': '2024-01-10T09:15:30Z',
                                    'updated_at': '2024-01-15T14:20:45Z'
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name='Пустой список целей',
                        summary='Когда в челлендже нет целей',
                        value={
                            'count': 0,
                            'next': None,
                            'previous': None,
                            'results': []
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Челленджи']
    )
    @action(detail=False, methods=['get'], url_path='challenge_goals/(?P<challenge_id>[^/.]+)')
    def challenge_goals(self, request, challenge_id=None):
        try:
            Challenge.objects.get(id=challenge_id)
        except Challenge.DoesNotExist:
            return Response(
                {'error': 'Челлендж не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        goals = Goal.objects.raw('''
                        SELECT g.id, g.user_id, g.title, g.description,
                               g.category_id, g.target_value, g.deadline, g.is_completed,
                               g.is_public, g.created_at, g.updated_at
                        FROM goals g
                        JOIN goal_challenges gc ON g.id = gc.goal_id 
                        WHERE gc.challenge_id = %s AND g.is_public = true''', (challenge_id,))

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(goals, request)

        if page is not None:
            serializer = GoalSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = GoalSerializer(goals, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary='Получить челленджи с участием цели',
        description='''
            Получение челленджей цели

            Получить список всех челленджей, в которых участвует данная цель по её ID.

            Права доступа:
            - Требуется действительный токен
            - Пользователь может просматривать челленджи своих целей
            - Администратор может просматривать челленджи любых целей
            - Обычные пользователи могут просматривать челленджи только публичных целей

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            ''',
        parameters=[
            OpenApiParameter(
                name='goal_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID цели, чьи челленджи запрашиваются'
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
                response=ChallengeSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Список челленджей цели',
                        summary='Стандартный ответ со списком челленджей',
                        value={
                            'count': 3,
                            'next': None,
                            'previous': None,
                            'results': [
                                {
                                    'id': 1,
                                    'name': 'Зимний фитнес-челлендж',
                                    'description': 'Тренировки всю зиму',
                                    'start_date': '2024-01-01',
                                    'end_date': '2024-03-31',
                                    'is_active': True,
                                    'created_at': '2024-01-10T09:15:30Z',
                                    'updated_at': '2024-01-15T14:20:45Z'
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name='Пустой список челленджей',
                        summary='Когда цель не участвует в челленджах',
                        value={
                            'count': 0,
                            'next': None,
                            'previous': None,
                            'results': []
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Челленджи']
    )
    @action(detail=False, methods=['get'], url_path='challenges_by_goal/(?P<goal_id>[^/.]+)')
    def goal_challenges(self, request, goal_id=None):
        try:
            goal = Goal.objects.get(id=goal_id)
        except Goal.DoesNotExist:
            return Response(
                {'error': 'Цель не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not goal.is_public:
            return Response(
                {'error': 'Цель недоступна'},
                status=status.HTTP_403_FORBIDDEN
            )

        challenges = Challenge.objects.raw('''
                        SELECT c.id, c.name, c.description, 
                               c.start_date, c.end_date, c.is_active, c.created_at, c.updated_at 
                        FROM challenges c
                        JOIN goal_challenges gc ON c.id = gc.challenge_id
                        WHERE gc.goal_id = %s''', (goal_id,))

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(challenges, request)

        if page is not None:
            serializer = ChallengeSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = ChallengeSerializer(challenges, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary='Получить челленджи с участием пользователя',
        description='''
            Получение челленджей пользователя

            Получить список всех челленджей, в которых участвуют цели данного пользователя по его ID.

            Права доступа:
            - Требуется действительный токен
            - Пользователь может просматривать свои челленджи
            - Администратор может просматривать челленджи любого пользователя
            - Обычные пользователи могут просматривать челленджи только публичных пользователей

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            ''',
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID пользователя, чьи челленджи запрашиваются'
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
                response=ChallengeSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Список челленджей пользователя',
                        summary='Стандартный ответ со списком челленджей',
                        value={
                            'count': 5,
                            'next': None,
                            'previous': None,
                            'results': [
                                {
                                    'id': 1,
                                    'name': 'Зимний фитнес-челлендж',
                                    'description': 'Тренировки всю зиму',
                                    'start_date': '2024-01-01',
                                    'end_date': '2024-03-31',
                                    'is_active': True,
                                    'created_at': '2024-01-10T09:15:30Z',
                                    'updated_at': '2024-01-15T14:20:45Z'
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name='Пустой список челленджей',
                        summary='Когда пользователь не участвует в челленджах',
                        value={
                            'count': 0,
                            'next': None,
                            'previous': None,
                            'results': []
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Челленджи']
    )
    @action(detail=False, methods=['get'], url_path='challenges_by_user/(?P<user_id>[^/.]+)')
    def user_challenges(self, request, user_id=None):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Пользователь не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not user.is_public:
            return Response(
                {'error': 'Пользователь недоступен'},
                status=status.HTTP_403_FORBIDDEN
            )

        challenges = Challenge.objects.raw('''
                            SELECT c.id, c.name, c.description, 
                                   c.start_date, c.end_date, c.is_active, c.created_at, c.updated_at 
                            FROM challenges c
                            JOIN goal_challenges gc ON c.id = gc.challenge_id
                            JOIN goals g ON g.id = gc.goal_id
                            WHERE g.user_id = %s''', (user_id,))

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(challenges, request)

        if page is not None:
            serializer = ChallengeSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = ChallengeSerializer(challenges, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary='Получить список целей-лидеров',
        description='''
            Получение лидерборда целей в челлендже

            Получить список целей, участвующих в челлендже, отсортированных по прогрессу выполнения.

            Особенности:
            - Сортировка по прогрессу min_diff (разница между target_value и текущим прогрессом)
            - Возвращаются только публичные цели (is_public=true)

            Права доступа:
            - Требуется действительный токен

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            ''',
        parameters=[
            OpenApiParameter(
                name='challenge_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID челленджа'
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
                response=GoalLeaderboardSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Лидерборд целей',
                        summary='Стандартный ответ со списком целей-лидеров',
                        value={
                            'count': 50,
                            'next': 'http://127.0.0.1:8080/api/challenges/goal_leaderboard/1/?limit=10&offset=10',
                            'previous': None,
                            'results': [
                                {
                                    'rank': 1,
                                    'min_diff': 5,
                                    'id': 5,
                                    'user_id': 123,
                                    'username': 'john_doe',
                                    'title': 'Бег 5 км',
                                    'description': 'Ежедневный бег 5 километров',
                                    'category_id': 1,
                                    'target_value': 150.000,
                                    'deadline': '2024-01-31',
                                    'is_completed': False,
                                    'is_public': True,
                                    'created_at': '2024-01-01T09:15:30Z',
                                    'updated_at': '2024-01-15T14:20:45Z'
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name='Пустой лидерборд',
                        summary='Когда в челлендже нет целей',
                        value={
                            'count': 0,
                            'next': None,
                            'previous': None,
                            'results': []
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Челленджи']
    )
    @action(detail=False, methods=['get'], url_path='goal_leaderboard/(?P<challenge_id>[^/.]+)')
    def goal_leaderboard(self, request, challenge_id=None):
        try:
            Challenge.objects.get(id=challenge_id)
        except Challenge.DoesNotExist:
            return Response(
                {'error': 'Челлендж не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        goals = Goal.objects.raw('''
                        SELECT
                            ROW_NUMBER() OVER (ORDER BY calculate_goal_progress(g.id)) AS rank,
                            g.id, 
                            g.user_id,
                            u.username,
                            g.title, 
                            g.description,
                            g.category_id, 
                            g.target_value, 
                            g.deadline, 
                            g.is_completed,
                            g.is_public, 
                            g.created_at, 
                            g.updated_at,
                            calculate_goal_progress(g.id) AS min_diff
                        FROM goals g
                        JOIN goal_challenges gc ON g.id = gc.goal_id
                        JOIN users u ON g.user_id = u.id
                        WHERE gc.challenge_id = %s
                            AND g.is_public = true
                        ORDER BY min_diff
                        ''', (challenge_id,))

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(goals, request)

        if page is not None:
            serializer = GoalLeaderboardSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = GoalLeaderboardSerializer(goals, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary='Получить список участников-лидеров',
        description='''
            Получение лидерборда участников в челлендже

            Получить список участников челленджа, отсортированных по лучшему прогрессу их целей.

            Особенности:
            - Сортировка по user_best_min_diff (лучший прогресс среди всех целей пользователя)
            - Возвращаются только пользователи с публичными целями
            - Для каждого пользователя рассчитывается статистика по целям
            - total_goals: общее количество целей пользователя в челлендже
            - goals_with_progress: цели, у которых есть записи прогресса
            - goals_without_progress: цели без записей прогресса

            Права доступа:
            - Требуется действительный токен

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            ''',
        parameters=[
            OpenApiParameter(
                name='challenge_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID челленджа'
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
                response=UserLeaderboardSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Лидерборд участников',
                        summary='Стандартный ответ со списком участников-лидеров',
                        value={
                            'count': 30,
                            'next': 'http://127.0.0.1:8080/api/challenges/user_leaderboard/1/?limit=10&offset=10',
                            'previous': None,
                            'results': [
                                {
                                    'id': 123,
                                    'username': 'john_doe',
                                    'user_rank': 1,
                                    'user_best_min_diff': 5,
                                    'total_goals': 3,
                                    'goals_with_progress': 3,
                                    'goals_without_progress': 0
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name='Пустой лидерборд',
                        summary='Когда в челлендже нет участников',
                        value={
                            'count': 0,
                            'next': None,
                            'previous': None,
                            'results': []
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Челленджи']
    )
    @action(detail=False, methods=['get'], url_path='user_leaderboard/(?P<challenge_id>[^/.]+)')
    def user_leaderboard(self, request, challenge_id=None):
        try:
            Challenge.objects.get(id=challenge_id)
        except Challenge.DoesNotExist:
            return Response(
                {'error': 'Челлендж не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        users = User.objects.raw('''
                            WITH user_best_diffs AS (
                                SELECT 
                                    g.user_id,
                                    u.username,
                                    MIN(calculate_goal_progress(g.id)) AS user_best_min_diff,
                                    COUNT(DISTINCT g.id) AS total_goals,
                                    COUNT(DISTINCT CASE WHEN EXISTS (
                                        SELECT 1 FROM goal_progresses gp 
                                        WHERE gp.goal_id = g.id
                                    ) THEN g.id END) AS goals_with_progress
                                FROM goals g
                                JOIN goal_challenges gc ON g.id = gc.goal_id
                                JOIN users u ON g.user_id = u.id
                                WHERE gc.challenge_id = %s
                                    AND g.is_public = true
                                GROUP BY g.user_id, u.username
                            )
                            SELECT
                                ROW_NUMBER() OVER (
                                    ORDER BY
                                        user_best_min_diff,
                                        username
                                ) AS user_rank,
                                user_id as id,
                                username,
                                user_best_min_diff,
                                total_goals,
                                goals_with_progress,
                                total_goals - goals_with_progress AS goals_without_progress
                            FROM user_best_diffs
                            ORDER BY user_rank;
                            ''', (challenge_id,))

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(users, request)

        if page is not None:
            serializer = UserLeaderboardSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = UserLeaderboardSerializer(users, many=True)
        return Response(serializer.data)


class AppendCategoryToChallengeView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken, IsAdmin]

    @extend_schema(
        summary='Добавить категорию к челленджу',
        description='''
            Добавление категории к челленджу

            Создает связь между существующим челленджем и категорией.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут добавлять категории к челленджам

            Параметры запроса:
            - challenge_id: ID существующего челленджа
            - category_id: ID существующей категории

            Валидация:
            - Проверка существования челленджа и категории
            - Проверка уникальности связи (нельзя добавить уже существующую связь)
            - Проверка типов данных параметров
            ''',
        parameters=[
            OpenApiParameter(
                name='challenge_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID челленджа',
                required=True
            ),
            OpenApiParameter(
                name='category_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID добавляемой категории',
                required=True
            )
        ],
        responses={
            201: OpenApiResponse(
                description='Created'
            ),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Челленджи']
    )
    def post(self, request):
        challenge_id = request.query_params.get('challenge_id')
        category_id = request.query_params.get('category_id')

        if not challenge_id or not category_id:
            return Response(
                {'error': 'Необходимы параметры challenge_id и category_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            challenge_id = int(challenge_id)
            category_id = int(category_id)
        except (ValueError, TypeError):
            return Response(
                {'error': 'ID должны быть целыми числами'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            challenge = Challenge.objects.get(id=challenge_id)
            category = Category.objects.get(id=category_id)
        except Challenge.DoesNotExist:
            return Response(
                {'error': 'Челлендж не найден'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Category.DoesNotExist:
            return Response(
                {'error': 'Категория не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

        existing_bundle = ChallengeCategory.objects.filter(
            challenge=challenge,
            category=category
        ).first()

        if existing_bundle:
            return Response(
                {'error': 'Категория уже добавлена'},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = {
            'challenge': challenge_id,
            'category': category_id
        }

        serializer = AppendCategoryToChallengeSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(status=status.HTTP_201_CREATED)


class DeleteCategoryFromChallengeView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken, IsAdmin]

    @extend_schema(
        summary='Удалить категорию у челленджа',
        description='''
            Удаление категории у челленджа

            Удаляет связь между существующим челленджем и категорией.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут удалять категории у челленджей

            Параметры запроса:
            - challenge_id: ID существующего челленджа
            - category_id: ID удаляемой категории

            Валидация:
            - Проверка существования челленджа и категории
            - Проверка существования связи (нельзя удалить несуществующую связь)
            - Проверка типов данных параметров
            ''',
        parameters=[
            OpenApiParameter(
                name='challenge_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID челленджа',
                required=True
            ),
            OpenApiParameter(
                name='category_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID удаляемой категории',
                required=True
            )
        ],
        responses={
            204: OpenApiResponse(
                description='No Content'
            ),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Челленджи']
    )
    def delete(self, request):
        challenge_id = request.query_params.get('challenge_id')
        category_id = request.query_params.get('category_id')

        if not challenge_id or not category_id:
            return Response(
                {'error': 'Необходимы параметры challenge_id и category_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            challenge_id = int(challenge_id)
            category_id = int(category_id)
        except (ValueError, TypeError):
            return Response(
                {'error': 'ID должны быть целыми числами'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            challenge = Challenge.objects.get(id=challenge_id)
            category = Category.objects.get(id=category_id)
        except Challenge.DoesNotExist:
            return Response(
                {'error': 'Челлендж не найден'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Category.DoesNotExist:
            return Response(
                {'error': 'Категория не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

        existing_bundle = ChallengeCategory.objects.filter(
            challenge=challenge,
            category=category
        ).first()

        if not existing_bundle:
            return Response(
                {'error': 'Удаляемая категория не была добавлена'},
                status=status.HTTP_400_BAD_REQUEST
            )

        existing_bundle.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class AppendGoalToChallengeView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken]

    @extend_schema(
        summary='Присоединить цель к челленджу',
        description='''
            Присоединение цели к челленджу

            Создает связь между существующей целью и челленджем.

            Права доступа:
            - Требуется действительный токен
            - Владелец цели может присоединять свои цели
            - Администратор может присоединять любые цели

            Параметры запроса:
            - goal_id: ID существующей цели
            - challenge_id: ID существующего челленджа

            Валидация:
            - Проверка существования цели и челленджа
            - Проверка уникальности связи
            - Цель должна быть публичной и принадлежать пользователю (не админу)
            - Дедлайн цели должен быть в будущем
            - Цель не должна быть завершена
            - Челлендж должен быть активен и доступен для присоединения
            - Категория цели должна участвовать в челлендже
            ''',
        parameters=[
            OpenApiParameter(
                name='goal_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID цели',
                required=True
            ),
            OpenApiParameter(
                name='challenge_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID челленджа',
                required=True
            )
        ],
        responses={
            201: OpenApiResponse(
                response=GoalChallengeSerializer,
                description='Created',
                examples=[
                    OpenApiExample(
                        name='Цель успешно присоединена',
                        summary='Цель успешно связана с челленджем',
                        value={
                            'goal': 5,
                            'challenge': 1,
                            'joined_at': '2024-01-15T10:30:00Z'
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
        tags=['Челленджи']
    )
    def post(self, request):
        goal_id = request.query_params.get('goal_id')
        challenge_id = request.query_params.get('challenge_id')

        if not challenge_id or not goal_id:
            return Response(
                {'error': 'Необходимы параметры challenge_id и goal_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            challenge_id = int(challenge_id)
            goal_id = int(goal_id)
        except (ValueError, TypeError):
            return Response(
                {'error': 'ID должны быть целыми числами'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            challenge = Challenge.objects.get(id=challenge_id)
            goal = Goal.objects.get(id=goal_id)
        except Challenge.DoesNotExist:
            return Response(
                {'error': 'Челлендж не найден'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Goal.DoesNotExist:
            return Response(
                {'error': 'Категория не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

        if goal.user != request.user and request.user.role != User.UserRole.ADMIN:
            return Response(
                {'error': 'Нельзя присоединить цель другого пользователя'},
                status=status.HTTP_403_FORBIDDEN
            )

        if not goal.is_public or not goal.user.is_public:
            return Response(
                {'error': 'Нельзя присоединить приватную цель или цель приватного пользователя'},
                status=status.HTTP_403_FORBIDDEN
            )

        if goal.deadline < timezone.now().date():
            return Response(
                {'error': 'Невозможно присоединить цель с пройденным дедлайном'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if goal.is_completed:
            return Response(
                {'error': 'Невозможно присоединить достигнутую цель'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not challenge.start_date <= timezone.now().date() <= challenge.end_date or not challenge.is_active:
            if not challenge.is_active:
                challenge.is_active = False
                challenge.save()
            return Response(
                {'error': 'В настоящий момент челлендж недоступен для присоединения'},
                status=status.HTTP_400_BAD_REQUEST
            )

        categories = ChallengeCategory.objects.filter(challenge=challenge).values_list('category', flat=True)
        if goal.category.id not in categories or not len(categories):
            return Response(
                {'error': 'Цели с данной категорией не участвуют в челлендже'},
                status=status.HTTP_400_BAD_REQUEST
            )

        existing_bundle = GoalChallenge.objects.filter(
            challenge=challenge,
            goal=goal
        ).first()

        if existing_bundle:
            return Response(
                {'error': 'Цель уже присоединилась к челленджу'},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = {
            'goal': goal_id,
            'challenge': challenge_id
        }

        serializer = AppendGoalToChallengeSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        result_serializer = GoalChallengeSerializer(result)
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)


class DeleteGoalFromChallengeView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken]

    @extend_schema(
        summary='Исключить цель из челленджа',
        description='''
            Исключение цели из челленджа

            Удаляет связь между существующей целью и челленджем.

            Права доступа:
            - Требуется действительный токен
            - Владелец цели может исключать свои цели
            - Администратор может исключать любые цели

            Параметры запроса:
            - goal_id: ID существующей цели
            - challenge_id: ID существующего челленджа

            Валидация:
            - Проверка существования цели и челленджа
            - Проверка существования связи
            - Только владелец цели или администратор могут исключать цель
            ''',
        parameters=[
            OpenApiParameter(
                name='goal_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID цели',
                required=True
            ),
            OpenApiParameter(
                name='challenge_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID челленджа',
                required=True
            )
        ],
        responses={
            204: OpenApiResponse(
                description='No Content',
                examples=[
                    OpenApiExample(
                        name='Цель успешно исключена',
                        summary='Связь успешно удалена',
                        value=None
                    )
                ]
            ),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Челленджи']
    )
    def delete(self, request):
        goal_id = request.query_params.get('goal_id')
        challenge_id = request.query_params.get('challenge_id')

        if not challenge_id or not goal_id:
            return Response(
                {'error': 'Необходимы параметры challenge_id и goal_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            challenge_id = int(challenge_id)
            goal_id = int(goal_id)
        except (ValueError, TypeError):
            return Response(
                {'error': 'ID должны быть целыми числами'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            challenge = Challenge.objects.get(id=challenge_id)
            goal = Goal.objects.get(id=goal_id)
        except Challenge.DoesNotExist:
            return Response(
                {'error': 'Челлендж не найден'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Goal.DoesNotExist:
            return Response(
                {'error': 'Категория не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

        if goal.user != request.user and request.user.role != User.UserRole.ADMIN:
            return Response(
                {'error': 'Нельзя исключить цель другого пользователя'},
                status=status.HTTP_403_FORBIDDEN
            )

        existing_bundle = GoalChallenge.objects.filter(
            challenge=challenge,
            goal=goal
        ).first()

        if not existing_bundle:
            return Response(
                {'error': 'Цель не участвует в челлендже'},
                status=status.HTTP_400_BAD_REQUEST
            )

        existing_bundle.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BatchChallengeCreateView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken, IsAdmin]

    @extend_schema(
        summary='Батчевая загрузка челленджей',
        description='''
            Массовое создание челленджей

            Создание нескольких челленджей за одну операцию с использованием bulk_create.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут создавать челленджи батчами

            Структура запроса:
            - challenges: Список объектов челленджей (максимум 10,000)
            - batch_size: Размер пачки для обработки (от 1 до 5,000, по умолчанию 100)

            Обязательные поля для каждого челленджа:
            - name: Название челленджа (строка, максимум 255 символов, не может быть пустой)
            - start_date: Дата начала (в формате YYYY-MM-DD)
            - end_date: Дата окончания (в формате YYYY-MM-DD)

            Опциональные поля:
            - description: Описание челленджа (текст, может быть null)
            - is_active: Активен ли челлендж (булево значение, по умолчанию true)
            - category_ids: Список ID категорий для связи с челленджем
            - goal_ids: Список ID целей для связи с челленджем

            Валидация:
            - Проверка обязательных полей
            - Проверка форматов дат
            - Проверка, что end_date не раньше start_date
            - Проверка существования категорий и целей
            - Удаление дубликатов в списках ID
            ''',
        request=BatchChallengeCreateSerializer,
        responses={
            200: OpenApiResponse(
                response=BatchOperationLogSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Полностью успешная операция',
                        summary='Все челленджи созданы',
                        value={
                            'total_processed': 100,
                            'successful': 100,
                            'failed': 0,
                            'batch_size': 50,
                            'errors': [],
                            'created_ids': [101, 102, 103, 104, 105],
                            'batches_processed': 2
                        }
                    ),
                    OpenApiExample(
                        name='Операция с ошибками',
                        summary='Некоторые челленджи не созданы',
                        value={
                            'total_processed': 5,
                            'successful': 3,
                            'failed': 2,
                            'batch_size': 100,
                            'errors': [
                                {
                                    'data': {
                                        'name': 'Марафон бега',
                                        'start_date': '2024-01-01',
                                        'end_date': '2023-12-31'
                                    },
                                    'error': 'end_date (2023-12-31) не может быть раньше start_date (2024-01-01)',
                                    'type': 'validation_error'
                                },
                                {
                                    'data': {
                                        'start_date': '2024-01-01',
                                        'end_date': '2024-01-31'
                                    },
                                    'error': 'Обязательные поля отсутствуют: name',
                                    'type': 'validation_error'
                                }
                            ],
                            'created_ids': [106, 107, 108],
                            'batches_processed': 1
                        }
                    )
                ]
            ),
            400: BAD_BATCH_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Челленджи']
    )
    def post(self, request):
        serializer = BatchChallengeCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Ошибка валидации',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        challenges_data = serializer.validated_data['challenges']
        batch_size = serializer.validated_data['batch_size']

        operation_log = {
            'total_processed': len(challenges_data),
            'successful': 0,
            'failed': 0,
            'errors': [],
            'created_ids': [],
            'batches_processed': 0,
            'batch_size': batch_size
        }

        try:
            validated_challenges_data = []
            challenge_data_by_index = {}

            for i, challenge_data in enumerate(challenges_data):
                try:
                    processed_data = challenge_data.copy()

                    required_fields = ['name', 'target_value', 'start_date', 'end_date']
                    missing_fields = []

                    for field in required_fields:
                        if field not in processed_data:
                            missing_fields.append(field)

                    if missing_fields:
                        raise ValueError(f'Обязательные поля отсутствуют: {", ".join(missing_fields)}')

                    name = processed_data['name']
                    start_date = processed_data['start_date']
                    end_date = processed_data['end_date']

                    if not isinstance(name, str):
                        raise ValueError(f'name должен быть строкой, получено: {name}')

                    name = name.strip()
                    if not name:
                        raise ValueError('name не может быть пустой строкой')

                    if isinstance(start_date, str):
                        try:
                            processed_data['start_date'] = datetime.strptime(start_date, '%Y-%m-%d').date()
                        except ValueError:
                            raise ValueError(f'start_date должен быть в формате YYYY-MM-DD, получено: {start_date}')
                    elif not isinstance(start_date, date):
                        raise ValueError(f'start_date должен быть датой, получено: {start_date}')

                    if isinstance(end_date, str):
                        try:
                            processed_data['end_date'] = datetime.strptime(end_date, '%Y-%m-%d').date()
                        except ValueError:
                            raise ValueError(f'end_date должен быть в формате YYYY-MM-DD, получено: {end_date}')
                    elif not isinstance(end_date, date):
                        raise ValueError(f'end_date должен быть датой, получено: {end_date}')

                    if processed_data['end_date'] < processed_data['start_date']:
                        raise ValueError(f'end_date ({end_date}) не может быть раньше start_date ({start_date})')

                    if 'is_active' in processed_data:
                        is_active = processed_data['is_active']
                        if not isinstance(is_active, bool):
                            raise ValueError(f'is_active должен быть булевым значением, получено: {is_active}')
                    else:
                        processed_data['is_active'] = True

                    if 'description' in processed_data and processed_data['description'] is not None:
                        if not isinstance(processed_data['description'], str):
                            raise ValueError(
                                f'description должен быть строкой, получено: {processed_data["description"]}')

                    category_ids = processed_data.get('category_ids', [])
                    if not isinstance(category_ids, list):
                        raise ValueError(f'category_ids должен быть списком, получено: {category_ids}')

                    validated_category_ids = []
                    seen_categories = set()
                    for cat_id in category_ids:
                        try:
                            if isinstance(cat_id, str):
                                cat_id_int = int(cat_id)
                            elif isinstance(cat_id, int):
                                cat_id_int = cat_id
                            else:
                                continue

                            if cat_id_int not in seen_categories:
                                seen_categories.add(cat_id_int)
                                validated_category_ids.append(cat_id_int)
                        except ValueError:
                            continue
                    processed_data['category_ids'] = validated_category_ids

                    goal_ids = processed_data.get('goal_ids', [])
                    if not isinstance(goal_ids, list):
                        raise ValueError(f'goal_ids должен быть списком, получено: {goal_ids}')

                    validated_goal_ids = []
                    seen_goals = set()
                    for goal_id in goal_ids:
                        try:
                            if isinstance(goal_id, str):
                                goal_id_int = int(goal_id)
                            elif isinstance(goal_id, int):
                                goal_id_int = goal_id
                            else:
                                continue

                            if goal_id_int not in seen_goals:
                                seen_goals.add(goal_id_int)
                                validated_goal_ids.append(goal_id_int)
                        except ValueError:
                            continue
                    processed_data['goal_ids'] = validated_goal_ids

                    challenge_data_by_index[i] = {
                        'data': processed_data,
                        'category_ids': validated_category_ids,
                        'goal_ids': validated_goal_ids
                    }

                    validated_challenges_data.append({
                        'index': i,
                        'data': processed_data,
                        'name': name,
                        'category_ids': validated_category_ids,
                        'goal_ids': validated_goal_ids
                    })

                except serializers.ValidationError as e:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': challenge_data,
                        'error': e.detail,
                        'type': 'validation_error'
                    })
                    if i in challenge_data_by_index:
                        del challenge_data_by_index[i]
                except Exception as e:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': challenge_data,
                        'error': str(e),
                        'type': 'validation_error'
                    })
                    if i in challenge_data_by_index:
                        del challenge_data_by_index[i]

            if not challenge_data_by_index:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            all_category_ids = set()
            all_goal_ids = set()

            for item_data in challenge_data_by_index.values():
                all_category_ids.update(item_data['category_ids'])
                all_goal_ids.update(item_data['goal_ids'])

            existing_categories_dict = {cat.id: cat for cat in Category.objects.filter(id__in=all_category_ids)}

            existing_goals = Goal.objects.filter(id__in=all_goal_ids).select_related('category')
            existing_goals_dict = {}
            goal_categories_dict = {}

            for goal in existing_goals:
                existing_goals_dict[goal.id] = goal
                goal_categories_dict[goal.id] = goal.category_id

            challenges_to_create = []
            challenge_relations_by_index = {}

            for i, item_data in challenge_data_by_index.items():
                try:
                    challenge = Challenge(
                        name=item_data['data']['name'],
                        description=item_data['data'].get('description'),
                        start_date=item_data['data']['start_date'],
                        end_date=item_data['data']['end_date'],
                        is_active=item_data['data']['is_active'],
                        created_at=timezone.now(),
                        updated_at=timezone.now()
                    )
                    challenges_to_create.append(challenge)

                    challenge_relations_by_index[i] = {
                        'category_ids': item_data['category_ids'],
                        'goal_ids': item_data['goal_ids']
                    }

                except Exception as e:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': item_data['data'],
                        'error': f'Ошибка при создании объекта челленджа: {str(e)}',
                        'type': 'creation_error'
                    })
                    if i in challenge_relations_by_index:
                        del challenge_relations_by_index[i]

            if not challenges_to_create:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            with connection.cursor() as cursor:
                cursor.execute('ALTER TABLE challenges DISABLE TRIGGER audit_challenges_trigger')
                cursor.execute('ALTER TABLE challenge_categories DISABLE TRIGGER audit_challenge_categories_trigger')
                cursor.execute('ALTER TABLE goal_challenges DISABLE TRIGGER audit_goal_challenges_trigger')

            try:
                with transaction.atomic():
                    if challenges_to_create:
                        try:
                            created_challenges = Challenge.objects.bulk_create(
                                challenges_to_create,
                                batch_size=len(challenges_to_create)
                            )
                            operation_log['successful'] += len(created_challenges)

                            if created_challenges:
                                created_ids = [challenge.id for challenge in created_challenges]
                                operation_log['created_ids'].extend(created_ids)

                                challenge_categories_to_create = []
                                goal_challenges_to_create = []

                                for idx, challenge in enumerate(created_challenges):
                                    original_index = list(challenge_data_by_index.keys())[idx]
                                    relations = challenge_relations_by_index.get(original_index)

                                    if relations:
                                        challenge_category_ids_set = set(relations['category_ids'])

                                        for category_id in relations['category_ids']:
                                            if category_id in existing_categories_dict:
                                                challenge_category = ChallengeCategory(
                                                    challenge=challenge,
                                                    category=existing_categories_dict[category_id]
                                                )
                                                challenge_categories_to_create.append(challenge_category)

                                        for goal_id in relations['goal_ids']:
                                            if goal_id in existing_goals_dict:
                                                goal_category_id = goal_categories_dict.get(goal_id)

                                                if goal_category_id and goal_category_id in challenge_category_ids_set:
                                                    goal = existing_goals_dict[goal_id]
                                                    goal_challenge = GoalChallenge(
                                                        challenge=challenge,
                                                        goal=goal,
                                                        joined_at=timezone.now()
                                                    )
                                                    goal_challenges_to_create.append(goal_challenge)

                                if challenge_categories_to_create:
                                    unique_challenge_categories = {}
                                    for cc in challenge_categories_to_create:
                                        key = (cc.challenge_id, cc.category_id)
                                        unique_challenge_categories[key] = cc

                                    try:
                                        ChallengeCategory.objects.bulk_create(
                                            list(unique_challenge_categories.values()),
                                            batch_size=len(unique_challenge_categories)
                                        )
                                    except Exception as e:
                                        operation_log['errors'].append({
                                            'type': 'challenge_category_creation_error',
                                            'error': str(e)
                                        })

                                if goal_challenges_to_create:
                                    unique_goal_challenges = {}
                                    for gc in goal_challenges_to_create:
                                        key = (gc.goal_id, gc.challenge_id)
                                        unique_goal_challenges[key] = gc

                                    try:
                                        GoalChallenge.objects.bulk_create(
                                            list(unique_goal_challenges.values()),
                                            batch_size=len(unique_goal_challenges)
                                        )
                                    except Exception as e:
                                        operation_log['errors'].append({
                                            'type': 'goal_challenge_creation_error',
                                            'error': str(e)
                                        })

                        except IntegrityError as e:
                            operation_log['failed'] += len(challenges_to_create)
                            operation_log['errors'].append({
                                'type': 'integrity_error',
                                'error': 'Ошибка целостности при bulk_create челленджей',
                                'details': str(e)
                            })
                            raise
                        except Exception as e:
                            operation_log['failed'] += len(challenges_to_create)
                            operation_log['errors'].append({
                                'type': 'bulk_create_error',
                                'error': str(e)
                            })

            finally:
                with connection.cursor() as cursor:
                    cursor.execute('ALTER TABLE challenges ENABLE TRIGGER audit_challenges_trigger')
                    cursor.execute('ALTER TABLE challenge_categories ENABLE TRIGGER audit_challenge_categories_trigger')
                    cursor.execute('ALTER TABLE goal_challenges ENABLE TRIGGER audit_goal_challenges_trigger')

            operation_log['batches_processed'] += 1

        except Exception as e:
            operation_log['errors'].append({
                'type': 'critical',
                'error': str(e)
            })
            operation_log['failed'] = operation_log['total_processed'] - operation_log['successful']

        batch_log = BatchLog(
            table_name='challenges',
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
