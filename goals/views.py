from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from bdcw.authentication import TokenAuthentication, HasValidToken, IsAdminOrSelf, IsAdmin
from bdcw.error_responses import (BAD_REQUEST_RESPONSE, UNAUTHORIZED_RESPONSE, FORBIDDEN_RESPONSE, NOT_FOUND_RESPONSE,
                                  INTERNAL_SERVER_ERROR)
from categories.models import Category
from .models import Goal, GoalProgress
from core.models import User
from .serializers import GoalSerializer, GoalCreateSerializer, GoalPartialUpdateSerializer, GoalUpdateSerializer, \
    GoalProgressSerializer, GoalProgressCreateSerializer, GoalProgressUpdateSerializer, GoalProgressPartialUpdateSerializer
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
        summary="Список целей",
        description="Получить список всех целей",
        responses={200: GoalSerializer(many=True),
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Цели']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Создать цель",
        description="Создание новой цели",
        request=GoalCreateSerializer,
        responses={201: GoalSerializer,
                   400: BAD_REQUEST_RESPONSE,
                   500: INTERNAL_SERVER_ERROR
                   },
        tags=['Цели']
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Получить цель",
        description="Получить информацию о конкретной цели",
        responses={200: GoalSerializer,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Цели']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Обновить цель",
        description="Полное обновление информации о цели",
        request=GoalUpdateSerializer,
        responses={200: GoalSerializer,
                   400: BAD_REQUEST_RESPONSE,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Цели']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Частично обновить цель",
        description="Частичное обновление информации о цели",
        request=GoalPartialUpdateSerializer,
        responses={200: GoalSerializer,
                   400: BAD_REQUEST_RESPONSE,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Цели']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Удалить цель",
        description="Удаление цели",
        responses={204: None,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Цели']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Получить цели пользователя",
        description="Получить список всех целей конкретного пользователя по его ID",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID пользователя'
            )
        ],
        responses={
            200: GoalSerializer(many=True),
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
        description="Получить список всех целей с конкретной категорией по её ID",
        parameters=[
            OpenApiParameter(
                name='category_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID категории'
            )
        ],
        responses={
            200: GoalSerializer(many=True),
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
        description="Получить список всех состояний прогресса по всем целям всех пользователей",
        responses={200: GoalProgressSerializer(many=True),
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Прогресс по цели']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Создать новое состояние прогресса",
        description="Создание нового состояния прогресса по цели",
        request=GoalProgressCreateSerializer,
        responses={201: GoalProgressSerializer,
                   400: BAD_REQUEST_RESPONSE,
                   500: INTERNAL_SERVER_ERROR
                   },
        tags=['Прогресс по цели']
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Получить состояние прогресса",
        description="Получить информацию о конкретном состоянии прогресса",
        responses={200: GoalProgressSerializer,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Прогресс по цели']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Обновить состояние прогресса",
        description="Полное обновление информации о конкретном состоянии прогресса",
        request=GoalProgressUpdateSerializer,
        responses={200: GoalProgressSerializer,
                   400: BAD_REQUEST_RESPONSE,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Прогресс по цели']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Частично обновить состояние прогресса",
        description="Частичное обновление информации о конкретном состоянии прогресса",
        request=GoalProgressPartialUpdateSerializer,
        responses={200: GoalProgressSerializer,
                   400: BAD_REQUEST_RESPONSE,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Прогресс по цели']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Удалить состояние прогресса",
        description="Удаление состояния прогресса",
        responses={204: None,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Прогресс по цели']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Получить состояния прогресса по цели",
        description="Получить список всех состояний прогресса конкретной цели по её D",
        parameters=[
            OpenApiParameter(
                name='goal_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID цели'
            )
        ],
        responses={
            200: GoalProgressSerializer(many=True),
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

