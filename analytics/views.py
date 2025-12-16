from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from bdcw.authentication import TokenAuthentication, HasValidToken, IsAdminOrSelf, IsAdmin
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
        summary="Получить рейтинг пользователей по количеству достигнутых целей",
        description="Получения рейтинга пользователей по количеству достигнутых целей",
        responses={
            200: GetUsersByCompletedGoalsSerializer(many=True),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
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
        summary="Получить рейтинг пользователей по проценту соблюдения привычек",
        description="Получения рейтинга пользователей по проценту соблюдения привычек",
        responses={
            200: GetUsersByHabitsConsistencySerializer(many=True),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
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
        summary="Получить рейтинг пользователей по количеству подписчиков",
        description="Получения рейтинга пользователей по количеству подписчиков",
        responses={
            200: GetUsersBySubscribersCountSerializer(many=True),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
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
        summary="Получить рейтинг категорий по популярности",
        description="Получения рейтинга категорий по популярности",
        responses={
            200: GetCategoriesByPopularitySerializer(many=True),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
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
        summary="Получить рейтинг челленджей по популярности",
        description="Получения рейтинга челленджей по популярности",
        responses={
            200: GetChallengesByPopularitySerializer(many=True),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
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
