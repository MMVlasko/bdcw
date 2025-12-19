from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from rest_framework.response import Response
from rest_framework.views import APIView

from bdcw.authentication import TokenAuthentication, HasValidToken
from bdcw.error_responses import (BAD_REQUEST_RESPONSE, UNAUTHORIZED_RESPONSE, FORBIDDEN_RESPONSE, NOT_FOUND_RESPONSE,
                                  INTERNAL_SERVER_ERROR)
from categories.models import Category
from challenges.models import Challenge
from .serializers import GetUsersByCompletedGoalsSerializer, GetUsersByHabitsConsistencySerializer, \
    GetUsersBySubscribersCountSerializer, GetCategoriesByPopularitySerializer, GetChallengesByPopularitySerializer
from core.models import User
from rest_framework.pagination import LimitOffsetPagination


class AnalyticsLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 10
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 100


class GetUsersByCompletedGoalsView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken]
    pagination_class = AnalyticsLimitOffsetPagination

    @extend_schema(
        summary='олучить рейтинг пользователей по количеству достигнутых целей',
        description='''
            Получение рейтинга пользователей по количеству достигнутых целей

            Возвращает список пользователей, отсортированных по количеству завершенных целей.

            Права доступа:
            - Требуется действительный токен

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка

            Возвращаемые поля:
            - id: Идентификатор пользователя
            - username: Имя пользователя
            - achievements_count: Количество достигнутых целей
            - avg_progress_percent: Средний процент прогресса по всем целям
            - total_goals: Общее количество целей пользователя
            - rank: Ранг пользователя в рейтинге
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
                response=GetUsersByCompletedGoalsSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Рейтинг пользователей по достижениям',
                        summary='Стандартный ответ с рейтингом пользователей',
                        value={
                            'count': 50,
                            'next': 'http://127.0.0.1:8080/api/analytics/users-by-completed-goals/?limit=10&offset=10',
                            'previous': None,
                            'results': [
                                {
                                    'id': 123,
                                    'username': 'top_achiever',
                                    'achievements_count': 25,
                                    'avg_progress_percent': 85.5,
                                    'total_goals': 30,
                                    'rank': 1
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name='Пустой рейтинг',
                        summary='Когда нет данных для рейтинга',
                        value={
                            'count': 0,
                            'next': None,
                            'previous': None,
                            'results': []
                        }
                    )
                ]
            ),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Аналитика']
    )
    def get(self, request):
        users = User.objects.raw('''
                                    SELECT 
                            id,
                            username,
                            completed_goals as achievements_count,
                            ROUND(avg_goal_progress, 1) as avg_progress_percent,
                            total_goals,
                            ROW_NUMBER() OVER (ORDER BY completed_goals DESC, avg_goal_progress DESC) as rank
                        FROM user_progress_analytics
                        ORDER BY completed_goals DESC, avg_goal_progress DESC
                                    ''')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(users, request)

        if page is not None:
            serializer = GetUsersByCompletedGoalsSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = GetUsersByCompletedGoalsSerializer(users, many=True)
        return Response(serializer.data)


class GetUsersByHabitsConsistencyView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken]
    pagination_class = AnalyticsLimitOffsetPagination

    @extend_schema(
        summary='Получить рейтинг пользователей по проценту соблюдения привычек',
        description='''
                Получение рейтинга пользователей по проценту соблюдения привычек

                Возвращает список пользователей, отсортированных по проценту соблюдения привычек.

                Права доступа:
                - Требуется действительный токен

                Пагинация:
                - limit: Количество записей на странице (макс. 100)
                - offset: Смещение от начала списка

                Возвращаемые поля:
                - id: Идентификатор пользователя
                - username: Имя пользователя
                - habit_consistency_percent: Процент соблюдения привычек
                - active_habits: Количество активных привычек
                - total_habits: Общее количество привычек пользователя
                - rank: Ранг пользователя в рейтинге
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
                response=GetUsersByHabitsConsistencySerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Рейтинг пользователей по привычкам',
                        summary='Стандартный ответ с рейтингом соблюдения привычек',
                        value={
                            'count': 40,
                            'next': 'http://127.0.0.1:8080/api/analytics/users-by-habit'
                                    's-consistency/?limit=10&offset=10',
                            'previous': None,
                            'results': [
                                {
                                    'id': 456,
                                    'username': 'consistent_user',
                                    'habit_consistency_percent': 95.2,
                                    'active_habits': 7,
                                    'total_habits': 8,
                                    'rank': 1
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name='Пустой рейтинг по привычкам',
                        summary='Когда нет данных для рейтинга привычек',
                        value={
                            'count': 0,
                            'next': None,
                            'previous': None,
                            'results': []
                        }
                    )
                ]
            ),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Аналитика']
    )
    def get(self, request):
        users = User.objects.raw('''
                                    SELECT
                                id,
                                username,
                                ROUND(avg_habit_consistency, 1) as habit_consistency_percent,
                                active_habits, total_habits,
                                ROW_NUMBER() OVER (ORDER BY avg_habit_consistency DESC) as rank
                            FROM user_progress_analytics
                            ORDER BY avg_habit_consistency DESC
                                    ''')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(users, request)

        if page is not None:
            serializer = GetUsersByHabitsConsistencySerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = GetUsersByHabitsConsistencySerializer(users, many=True)
        return Response(serializer.data)


class GetUsersBySubscribersCountView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken]
    pagination_class = AnalyticsLimitOffsetPagination

    @extend_schema(
        summary='Получить рейтинг пользователей по количеству подписчиков',
        description='''
            Получение рейтинга пользователей по количеству подписчиков

            Возвращает список пользователей, отсортированных по количеству подписчиков.

            Права доступа:
            - Требуется действительный токен

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка

            Возвращаемые поля:
            - id: Идентификатор пользователя
            - username: Имя пользователя
            - subscribers_count: Количество подписчиков
            - subscribing_count: Количество подписок пользователя
            - subscribers_rank: Ранг пользователя по количеству подписчиков
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
                response=GetUsersBySubscribersCountSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Рейтинг пользователей по подписчикам',
                        summary='Стандартный ответ с рейтингом по подписчикам',
                        value={
                            'count': 35,
                            'next': None,
                            'previous': None,
                            'results': [
                                {
                                    'id': 789,
                                    'username': 'popular_user',
                                    'subscribers_count': 125,
                                    'subscribing_count': 45,
                                    'subscribers_rank': 1
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name='Пустой рейтинг по подписчикам',
                        summary='Когда нет данных для рейтинга подписчиков',
                        value={
                            'count': 0,
                            'next': None,
                            'previous': None,
                            'results': []
                        }
                    )
                ]
            ),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Аналитика']
    )
    def get(self, request):
        users = User.objects.raw('''
                                    SELECT
                                id,
                                username,
                                subscribers_count,
                                subscribing_count,
                                ROW_NUMBER() OVER (ORDER BY subscribers_count DESC) as subscribers_rank
                            FROM user_progress_analytics
                            ORDER BY subscribers_count DESC
                                    ''')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(users, request)

        if page is not None:
            serializer = GetUsersBySubscribersCountSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = GetUsersByCompletedGoalsSerializer(users, many=True)
        return Response(serializer.data)


class GetCategoriesByPopularityView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken]
    pagination_class = AnalyticsLimitOffsetPagination

    @extend_schema(
        summary='Получить рейтинг категорий по популярности',
        description='''
            Получение рейтинга категорий по популярности

            Возвращает список категорий, отсортированных по популярности и активности.

            Права доступа:
            - Требуется действительный токен

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка

            Возвращаемые поля:
            - id: Идентификатор категории
            - name: Название категории
            - total_goals: Общее количество целей в категории
            - total_habits: Общее количество привычек в категории
            - unique_users: Количество уникальных пользователей, использующих категорию
            - activity_score: Общий балл активности категории
            - rank: Ранг категории по популярности (взвешенный показатель)
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
                response=GetCategoriesByPopularitySerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Рейтинг категорий по популярности',
                        summary='Стандартный ответ с рейтингом категорий',
                        value={
                            'count': 20,
                            'next': None,
                            'previous': None,
                            'results': [
                                {
                                    'id': 1,
                                    'name': 'Спорт',
                                    'total_goals': 150,
                                    'total_habits': 75,
                                    'unique_users': 45,
                                    'activity_score': 89.5,
                                    'rank': 1
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name='Пустой рейтинг категорий',
                        summary='Когда нет данных для рейтинга категорий',
                        value={
                            'count': 0,
                            'next': None,
                            'previous': None,
                            'results': []
                        }
                    )
                ]
            ),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Аналитика']
    )
    def get(self, request):
        categories = Category.objects.raw('''
                                    SELECT
                                id,
                                name,
                                total_goals,
                                total_habits,
                                unique_users,
                                ROUND(activity_score, 1) as activity_score,
                                popularity_rank as rank
                            FROM category_detailed_analytics
                                ORDER BY popularity_rank
                                    ''')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(categories, request)

        if page is not None:
            serializer = GetCategoriesByPopularitySerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = GetCategoriesByPopularitySerializer(categories, many=True)
        return Response(serializer.data)


class GetChallengesByPopularityView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken]
    pagination_class = AnalyticsLimitOffsetPagination

    @extend_schema(
        summary='Получить рейтинг челленджей по популярности',
        description='''
            Получение рейтинга челленджей по популярности

            Возвращает список челленджей, отсортированных по популярности и активности.

            Права доступа:
            - Требуется действительный токен

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка

            Возвращаемые поля:
            - id: Идентификатор челленджа
            - name: Название челленджа
            - participants_count: Количество участников
            - goals_count: Количество целей в челлендже
            - is_active: Активен ли челлендж
            - avg_progress_percent: Средний процент прогресса участников
            - popularity_rank: Ранг челленджа по популярности
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
                response=GetChallengesByPopularitySerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Рейтинг челленджей по популярности',
                        summary='Стандартный ответ с рейтингом челленджей',
                        value={
                            'count': 15,
                            'next': None,
                            'previous': None,
                            'results': [
                                {
                                    'id': 1,
                                    'name': 'Марафон бега',
                                    'participants_count': 50,
                                    'goals_count': 60,
                                    'is_active': True,
                                    'avg_progress_percent': 65.3,
                                    'popularity_rank': 1
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name='Пустой рейтинг челленджей',
                        summary='Когда нет данных для рейтинга челленджей',
                        value={
                            'count': 0,
                            'next': None,
                            'previous': None,
                            'results': []
                        }
                    )
                ]
            ),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Аналитика']
    )
    def get(self, request):
        challenges = Challenge.objects.raw('''
                                    SELECT
                                        id,
                                        name,
                                        participants_count,
                                        goals_count,
                                        is_active,
                                        ROUND(avg_progress_percentage, 1) as avg_progress_percent,
                                        ROW_NUMBER() OVER (ORDER BY participants_count DESC, goals_count DESC) as popularity_rank
                                    FROM challenge_basic_analytics
                                    ORDER BY participants_count DESC
                                    ''')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(challenges, request)

        if page is not None:
            serializer = GetChallengesByPopularitySerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = GetChallengesByPopularitySerializer(challenges, many=True)
        return Response(serializer.data)
