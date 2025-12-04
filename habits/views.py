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
from .models import Habit, HabitLog
from core.models import User
from .serializers import HabitSerializer, HabitCreateSerializer, HabitUpdateSerializer, HabitPartialUpdateSerializer, \
    HabitLogSerializer, HabitLogCreateSerializer, HabitLogUpdateSerializer, HabitLogPartialUpdateSerializer
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
        summary="Список привычек",
        description="Получить список всех привычек",
        responses={200: HabitSerializer(many=True),
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Привычки']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Создать привычку",
        description="Создание новой привычки",
        request=HabitCreateSerializer,
        responses={201: HabitSerializer,
                   400: BAD_REQUEST_RESPONSE,
                   500: INTERNAL_SERVER_ERROR
                   },
        tags=['Привычки']
    )
    def create(self, request, *args, **kwargs):
        if request.data['user'] != request.user.id and request.user.role != User.UserRole.ADMIN:
            raise PermissionDenied('Нельзя создать привычку у другого пользователя')
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Получить привычку",
        description="Получить информацию о конкретной привычке",
        responses={200: HabitSerializer,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Привычки']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Обновить привычку",
        description="Полное обновление информации о привычке",
        request=HabitUpdateSerializer,
        responses={200: HabitSerializer,
                   400: BAD_REQUEST_RESPONSE,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Привычки']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Частично обновить привычку",
        description="Частичное обновление информации о привычке",
        request=HabitPartialUpdateSerializer,
        responses={200: HabitSerializer,
                   400: BAD_REQUEST_RESPONSE,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Привычки']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Удалить привычку",
        description="Удаление привычки",
        responses={204: None,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Привычки']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Получить привычки пользователя",
        description="Получить список всех привычек конкретного пользователя по его ID",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID пользователя'
            )
        ],
        responses={
            200: HabitSerializer(many=True),
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
        description="Получить список всех привычек с конкретной категорией по её ID",
        parameters=[
            OpenApiParameter(
                name='category_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID категории'
            )
        ],
        responses={
            200: HabitSerializer(many=True),
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
        description="Получить список всех логов соблюдения привычек по всем привычкам всех пользователей",
        responses={200: HabitLogSerializer(many=True),
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Логи соблюдения привычки']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Создать новый лог соблюдения привычки",
        description="Создание нового лога соблюдения привычки",
        request=HabitLogCreateSerializer,
        responses={201: HabitLogSerializer,
                   400: BAD_REQUEST_RESPONSE,
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
        description="Получить информацию о конкретном логе соблюдения привычки",
        responses={200: HabitLogSerializer,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Логи соблюдения привычки']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Обновить лог соблюдения привычки",
        description="Полное обновление информации о конкретном логе соблюдения привычки",
        request=HabitLogUpdateSerializer,
        responses={200: HabitLogSerializer,
                   400: BAD_REQUEST_RESPONSE,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Логи соблюдения привычки']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Частично обновить лог соблюдения привычки",
        description="Частичное обновление информации о конкретном логt соблюдения привычки",
        request=HabitLogPartialUpdateSerializer,
        responses={200: HabitLogSerializer,
                   400: BAD_REQUEST_RESPONSE,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Логи соблюдения привычки']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Удалить состояние лог соблюдения привычки",
        description="Удаление состояния лог соблюдения привычки",
        responses={204: None,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Логи соблюдения привычки']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Получить логи соблюдения привычки",
        description="Получить список всех логов по конкретной привычке по её ID",
        parameters=[
            OpenApiParameter(
                name='habit_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID привычки'
            )
        ],
        responses={
            200: HabitLogSerializer(many=True),
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

        current_user = request.user

        if current_user == habit.user or current_user.role == User.UserRole.ADMIN:
            habit_logs = HabitLog.objects.filter(habit=habit)
        else:
            raise PermissionDenied('Нет доступа к приватным целям')

        page = self.paginate_queryset(habit_logs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(habit_logs, many=True)
        return Response(serializer.data)

