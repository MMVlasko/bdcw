from drf_spectacular.utils import extend_schema
from rest_framework import viewsets

from bdcw.authentication import TokenAuthentication, HasValidToken, IsAdminOrSelf, IsAdmin
from bdcw.error_responses import (BAD_REQUEST_RESPONSE, UNAUTHORIZED_RESPONSE, FORBIDDEN_RESPONSE, NOT_FOUND_RESPONSE,
                                  INTERNAL_SERVER_ERROR)
from .models import Category
from .serializers import CategorySerializer, CategoryCreateAndUpdateSerializer, CategoryPartialUpdateSerializer
from rest_framework.pagination import LimitOffsetPagination


class CategoryLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 10
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 100


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    pagination_class = CategoryLimitOffsetPagination
    authentication_classes = [TokenAuthentication]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [HasValidToken()]

        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [HasValidToken(), IsAdmin()]

        return [HasValidToken()]

    def get_serializer_class(self):
        return {
            'create': CategoryCreateAndUpdateSerializer,
            'update': CategoryCreateAndUpdateSerializer,
            'partial_update': CategoryPartialUpdateSerializer
        }.get(self.action, CategorySerializer)

    @extend_schema(
        summary="Список категорий",
        description="Получить список всех категорий",
        responses={200: CategorySerializer(many=True),
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Категории']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Создать категорию",
        description="Создание новой категории",
        request=CategoryCreateAndUpdateSerializer,
        responses={201: CategorySerializer,
                   400: BAD_REQUEST_RESPONSE,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   500: INTERNAL_SERVER_ERROR
                   },
        tags=['Категории']
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Получить категорию",
        description="Получить информацию о конкретной категории",
        responses={200: CategorySerializer,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Категории']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Обновить категорию",
        description="Полное обновление информации о категории",
        request=CategoryCreateAndUpdateSerializer,
        responses={200: CategorySerializer,
                   400: BAD_REQUEST_RESPONSE,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Категории']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Частично обновить категорию",
        description="Частичное обновление информации о категории",
        request=CategoryCreateAndUpdateSerializer,
        responses={200: CategorySerializer,
                   400: BAD_REQUEST_RESPONSE,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Категории']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Удалить категорию",
        description="Удалить категорию",
        responses={204: None,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Категории']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)