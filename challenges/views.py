from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.db import connection
from rest_framework.views import APIView

from bdcw.authentication import TokenAuthentication, HasValidToken, IsAdminOrSelf, IsAdmin
from bdcw.error_responses import (BAD_REQUEST_RESPONSE, UNAUTHORIZED_RESPONSE, FORBIDDEN_RESPONSE, NOT_FOUND_RESPONSE,
                                  INTERNAL_SERVER_ERROR)
from categories.models import Category
from categories.serializers import CategorySerializer
from core.serializers import UserSerializer
from goals.models import Goal
from goals.serializers import GoalSerializer
from .models import Challenge, GoalChallenge, ChallengeCategory
from core.models import User
from .serializers import ChallengeSerializer, ChallengeCreateAndUpdateSerializer, ChallengePartialUpdateSerializer, \
    AppendCategoryToChallengeSerializer, AppendGoalToChallengeSerializer, GoalChallengeSerializer, \
    GoalLeaderboardSerializer, UserLeaderboardSerializer
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
        summary="Список челленджей",
        description="Получить список всех челленджей",
        responses={200: ChallengeSerializer(many=True),
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Челленджи']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Создать челлендж",
        description="Создание нового челленджа",
        request=ChallengeCreateAndUpdateSerializer,
        responses={201: ChallengeSerializer,
                   400: BAD_REQUEST_RESPONSE,
                   500: INTERNAL_SERVER_ERROR
                   },
        tags=['Челленджи']
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Получить челлендж",
        description="Получить информацию о конкретном челлендже",
        responses={200: ChallengeSerializer,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Челленджи']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Обновить челлендж",
        description="Полное обновление информации о челлендже",
        request=ChallengeCreateAndUpdateSerializer,
        responses={200: ChallengeSerializer,
                   400: BAD_REQUEST_RESPONSE,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Челленджи']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Частично обновить челлендж",
        description="Частичное обновление информации о челлендже",
        request=ChallengePartialUpdateSerializer,
        responses={200: ChallengeSerializer,
                   400: BAD_REQUEST_RESPONSE,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Челленджи']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Удалить челлендж",
        description="Удаление челленджа",
        responses={204: None,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Челленджи']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Получить категории челленджа",
        description="Получить список всех категорий данного челленджа по его ID",
        parameters=[
            OpenApiParameter(
                name='challenge_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID челленджа'
            )
        ],
        responses={
            200: CategorySerializer(many=True),
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
        summary="Получить челленджи по категории",
        description="Получить список всех челленджей с данной категорией",
        parameters=[
            OpenApiParameter(
                name='category_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID категории'
            )
        ],
        responses={
            200: ChallengeSerializer(many=True),
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
        summary="Получить участников челленджа",
        description="Получить список всех участников данного челленджа",
        parameters=[
            OpenApiParameter(
                name='challenge_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID челленджа'
            )
        ],
        responses={
            200: UserSerializer(many=True),
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
        summary="Получить цели челленджа",
        description="Получить список всех целей, участвующих в данном челлендже",
        parameters=[
            OpenApiParameter(
                name='challenge_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID челленджа'
            )
        ],
        responses={
            200: GoalSerializer(many=True),
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
        summary="Получить челленджи с участием цели",
        description="Получить список челленджей, в которых участвует данная цель",
        parameters=[
            OpenApiParameter(
                name='goal_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID цели'
            )
        ],
        responses={
            200: ChallengeSerializer(many=True),
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
                        SELECT c.id, c.name, c.description, c.target_value, 
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
        summary="Получить челленджи с участием пользователя",
        description="Получить список челленджей, в которых участвует данный пользователь",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID пользователя'
            )
        ],
        responses={
            200: ChallengeSerializer(many=True),
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
                            SELECT c.id, c.name, c.description, c.target_value, 
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
        summary="Получить список целей-лидеров",
        description="Получить список целей в порядке лидирования в челлендже",
        parameters=[
            OpenApiParameter(
                name='challenge_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID челленджа'
            )
        ],
        responses={
            200: GoalLeaderboardSerializer(many=True),
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
                            ROW_NUMBER() OVER (ORDER BY
                                (
                                    SELECT MIN(ABS(gp.current_value - g.target_value))
                                    FROM goal_progresses gp
                                    WHERE gp.goal_id = g.id
                                )
                            ) AS rank,
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
                            (
                                SELECT MIN(ABS(gp.current_value - g.target_value))
                                FROM goal_progresses gp
                                WHERE gp.goal_id = g.id
                            ) AS min_diff
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
        summary="Получить список участников-лидеров",
        description="Получить список участников в порядке лидирования в челлендже",
        parameters=[
            OpenApiParameter(
                name='challenge_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID челленджа'
            )
        ],
        responses={
            200: GoalLeaderboardSerializer(many=True),
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
                                    MIN(
                                        (
                                            SELECT MIN(ABS(gp.current_value - g.target_value))
                                            FROM goal_progresses gp
                                            WHERE gp.goal_id = g.id
                                        )
                                    ) AS user_best_min_diff,
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
        summary="Добавить категорию к челленджу",
        description="Добавление новой категории к челленджу",
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
            201: None,
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
        summary="Удалить категорию у челленджа",
        description="Удаление существующей категории у челленджа",
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
            204: None,
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
        summary="Присоединить цель к челленджу",
        description="ДПрисоединение новой цели к челленджу",
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
            201: None,
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

        if (not goal.is_public or goal.user != request.user) and request.user.role != User.UserRole.ADMIN:
            return Response(
                {'error': 'Нельзя присоединить цель другого пользователя или приватную цель'},
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
        summary="Исключить цель из челленджа",
        description="Исключение цели из челленджа",
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
            201: None,
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
