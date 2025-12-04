from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiExample
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from bdcw.authentication import TokenAuthentication, HasValidToken, IsAdminOrSelf, IsAdmin
from bdcw.error_responses import (BAD_REQUEST_RESPONSE, UNAUTHORIZED_RESPONSE, FORBIDDEN_RESPONSE, NOT_FOUND_RESPONSE,
                                  INTERNAL_SERVER_ERROR)
from .models import User, AuthToken
from .serializers import UserSerializer, UserCreateSerializer, UserUpdateSerializer, UserChangePasswordSerializer, \
    UserPartialUpdateSerializer, LoginSerializer, LoginResponseSerializer
from rest_framework.pagination import LimitOffsetPagination


class UserLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 10
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 100


class UserViewSet(viewsets.ModelViewSet):
    pagination_class = UserLimitOffsetPagination
    authentication_classes = [TokenAuthentication]

    def get_permissions(self):
        if self.action == 'create':
            return []

        elif self.action in ['list', 'retrieve']:
            return [HasValidToken()]

        elif self.action in ['update', 'partial_update', 'change_password']:
            return [HasValidToken(), IsAdminOrSelf()]

        elif self.action == 'destroy':
            return [HasValidToken(), IsAdmin()]

        return [HasValidToken()]

    def get_queryset(self):
        user = self.request.user

        if self.action == 'list':
            if user.role != User.UserRole.ADMIN:
                return User.objects.filter(is_public=True)

        return User.objects.all()

    def get_serializer_class(self):
        return {
            'create': UserCreateSerializer,
            'update': UserUpdateSerializer,
            'partial_update': UserPartialUpdateSerializer,
        }.get(self.action, UserSerializer)

    @extend_schema(
        summary="Список пользователей",
        description="Получить список всех пользователей",
        responses={200: UserSerializer(many=True),
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Пользователи']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Создать пользователя",
        description="Регистрация нового пользователя",
        request=UserCreateSerializer,
        responses={201: UserSerializer,
                   400: BAD_REQUEST_RESPONSE,
                   500: INTERNAL_SERVER_ERROR
                   },
        examples=[
            OpenApiExample(
                'Пример создания пользователя',
                value={
                    'username': 'john_doe',
                    'password': 'SecurePass123',
                    'confirm_password': 'SecurePass123',
                    'first_name': 'John',
                    'last_name': 'Doe',
                    'description': 'Описание пользователя'
                },
                request_only=True
            )
        ],
        tags=['Пользователи']
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Получить пользователя",
        description="Получить информацию о конкретном пользователе",
        responses={200: UserSerializer,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Пользователи']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Обновить пользователя",
        description="Полное обновление информации пользователя",
        request=UserUpdateSerializer,
        responses={200: UserSerializer,
                   400: BAD_REQUEST_RESPONSE,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Пользователи']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Частично обновить пользователя",
        description="Частичное обновление информации пользователя",
        request=UserUpdateSerializer,
        responses={200: UserSerializer,
                   400: BAD_REQUEST_RESPONSE,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Пользователи']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Удалить пользователя",
        description="Удалить пользователя из системы",
        responses={204: None,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Пользователи']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Сменить пароль",
        description="Изменить пароль пользователя",
        request=UserChangePasswordSerializer,
        responses={200: None,
                   400: BAD_REQUEST_RESPONSE,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        examples=[
            OpenApiExample(
                'Пример смены пароля',
                value={
                    'password': 'NewSecurePass456',
                    'confirm_password': 'NewSecurePass456'
                },
                request_only=True
            )
        ],
        tags=['Пользователи']
    )
    @action(['put'], detail=True)
    def change_password(self, request, pk=None):
        user = self.get_object()
        serializer = UserChangePasswordSerializer(user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_200_OK)


class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary="Вход",
        description="Получить токен для авторизации",
        request=LoginSerializer,
        responses={
            200: LoginResponseSerializer,
            400: BAD_REQUEST_RESPONSE
        },
        tags=['Пользователи']
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data['user']

            token = AuthToken.create_token(user)

            user.last_login = timezone.now()
            user.save()

            return Response({
                'success': True,
                'message': 'Авторизация успешна',
                'token': token.key,
                'expires_at': token.expires_at,
                'user': UserSerializer(user).data
            })

        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken]

    @extend_schema(
        summary="Выход",
        description="Деактивировать токен для авторизации",
        responses={
            200: None,
            401: UNAUTHORIZED_RESPONSE
        },
        tags=['Пользователи']
    )
    def post(self, request):
        token = request.auth

        token.is_active = False
        token.save()

        return Response(status=status.HTTP_200_OK)


class CleanUnusedTokensView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken, IsAdmin]

    @extend_schema(
        summary="Очистка деактивированных токенов авторизации",
        description="Удалить все декативированные токены",
        responses={
            204: None,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE
        },
        tags=['Пользователи']
    )
    def delete(self, request):
        AuthToken.objects.filter(is_active=False).delete()

        return Response(status=status.HTTP_204_NO_CONTENT)