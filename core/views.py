from django.db import transaction, IntegrityError
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from bdcw.authentication import TokenAuthentication, HasValidToken, IsAdminOrSelf, IsAdmin
from bdcw.error_responses import (BAD_REQUEST_RESPONSE, UNAUTHORIZED_RESPONSE, FORBIDDEN_RESPONSE, NOT_FOUND_RESPONSE,
                                  INTERNAL_SERVER_ERROR, BAD_BATCH_REQUEST_RESPONSE)
from .models import User, AuthToken
from .serializers import UserSerializer, UserCreateSerializer, UserUpdateSerializer, UserChangePasswordSerializer, \
    UserPartialUpdateSerializer, LoginSerializer, LoginResponseSerializer, BatchUserCreateSerializer, \
    BatchOperationLogSerializer
from rest_framework.pagination import LimitOffsetPagination

from .validators import validate_password, validate_username


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

        elif self.action in ['destroy', 'change_role']:
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
        tags=['Пользователи']
    )
    @action(['put'], detail=True)
    def change_password(self, request, pk=None):
        user = self.get_object()
        serializer = UserChangePasswordSerializer(user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_200_OK)

    @extend_schema(
        summary="Сменить роль",
        description="Изменить роль пользователя",
        request=None,
        parameters=[
            OpenApiParameter(
                name='role',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Роль',
                required=True
            ),
        ],
        responses={200: None,
                   400: BAD_REQUEST_RESPONSE,
                   401: UNAUTHORIZED_RESPONSE,
                   403: FORBIDDEN_RESPONSE,
                   404: NOT_FOUND_RESPONSE,
                   500: INTERNAL_SERVER_ERROR},
        tags=['Пользователи']
    )
    @action(['put'], detail=True)
    def change_role(self, request):
        role = request.query_params.get('role')

        if not role:
            return Response(
                {'error': 'Необходим параметр role'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if role not in ('admin', 'user'):
            return Response(
                {'error': 'Роль должна быть admin или user'},
                status=status.HTTP_400_BAD_REQUEST
            )
        user = self.get_object()
        user.role = role
        user.save()
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


class BatchUserCreateView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken, IsAdmin]

    @extend_schema(
        summary="Батчевая загрузка пользователей",
        description="Создание нескольких пользователей за одну операцию с использованием bulk_create",
        request=BatchUserCreateSerializer,
        responses={
            200: BatchOperationLogSerializer,
            400: BAD_BATCH_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Пользователи']
    )
    def post(self, request):
        serializer = BatchUserCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Ошибка валидации',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        users_data = serializer.validated_data['users']
        batch_size = serializer.validated_data['batch_size']
        update_existing = serializer.validated_data['update_existing']

        operation_log = {
            'total_processed': len(users_data),
            'successful': 0,
            'failed': 0,
            'errors': [],
            'created_ids': [],
            'updated_ids': [],
            'batches_processed': 0,
            'batch_size': batch_size,
            'operation_time': 0.0
        }

        try:
            validated_users_data = []
            usernames_in_request = set()

            for i, user_data in enumerate(users_data):
                try:
                    username = user_data.get('username', '')

                    if username in usernames_in_request:
                        raise ValueError(f'Username "{username}" дублируется в этом запросе')
                    usernames_in_request.add(username)

                    validated_user = user_data.copy()

                    if 'confirm_password' not in validated_user:
                        validated_user['confirm_password'] = validated_user['password']

                    validate_password(
                        validated_user['password'],
                        validated_user['confirm_password']
                    )

                    validate_username(username)
                    validated_users_data.append({
                        'index': i,
                        'data': validated_user,
                        'username': username
                    })

                except serializers.ValidationError as e:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'index': i,
                        'username': user_data.get('username', 'unknown'),
                        'error': e.detail,
                        'type': 'validation_error'
                    })
                except Exception as e:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'index': i,
                        'username': user_data.get('username', 'unknown'),
                        'error': str(e),
                        'type': 'validation_error'
                    })

            if not validated_users_data:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            # Этап 2: Подготовка данных
            usernames = [item['username'] for item in validated_users_data]

            # Получаем существующих пользователей
            existing_users = {}

            # ВСЕГДА получаем существующих пользователей для любых режимов
            existing_qs = User.objects.filter(username__in=usernames)
            existing_users_dict = {user.username: user for user in existing_qs}
            existing_usernames = set(existing_users_dict.keys())

            # Фильтруем пользователей в зависимости от режима
            filtered_users = []
            users_to_update_dict = {}  # Для обновления
            new_users_data = []  # Для создания

            for item in validated_users_data:
                username = item['username']
                user_data = item['data']

                if username in existing_usernames:
                    # Пользователь существует
                    if update_existing:
                        # Будем обновлять
                        user = existing_users_dict[username]
                        # Подготавливаем данные для обновления
                        users_to_update_dict[username] = {
                            'user': user,
                            'data': user_data,
                            'original_index': item['index']
                        }
                        filtered_users.append(item)
                    else:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'index': item['index'],
                            'username': username,
                            'error': f'Пользователь с username "{username}" уже существует',
                            'type': 'duplicate_error'
                        })
                else:
                    # Новый пользователь
                    new_users_data.append({
                        'data': user_data,
                        'username': username,
                        'original_index': item['index']
                    })
                    filtered_users.append(item)

            # Этап 3: Обработка батчей
            batches = [
                filtered_users[i:i + batch_size]
                for i in range(0, len(filtered_users), batch_size)
            ]

            for batch_index, batch in enumerate(batches):
                users_to_create = []
                users_to_update = []

                for item in batch:
                    username = item['username']

                    if username in users_to_update_dict:
                        # Обновление существующего пользователя
                        update_info = users_to_update_dict[username]
                        user = update_info['user']
                        user_data = update_info['data']

                        # Обновляем поля
                        user.first_name = user_data.get('first_name', user.first_name)
                        user.last_name = user_data.get('last_name', user.last_name)
                        user.description = user_data.get('description', user.description)
                        user.is_public = user_data.get('is_public', user.is_public)
                        user.is_active = user_data.get('is_active', user.is_active)
                        user.updated_at = timezone.now()

                        # Обновляем пароль, если передан
                        if 'password' in user_data:
                            user.set_password(user_data['password'])

                        users_to_update.append(user)

                    else:
                        # Создание нового пользователя
                        user_data = item['data']
                        user = User(
                            username=username,
                            first_name=user_data['first_name'],
                            last_name=user_data['last_name'],
                            description=user_data.get('description'),
                            is_public=user_data.get('is_public', True),
                            is_active=user_data.get('is_active', True),
                            created_at=timezone.now(),
                            updated_at=timezone.now()
                        )

                        user.set_password(user_data['password'])
                        users_to_create.append(user)

                # Сохраняем батч
                with transaction.atomic():
                    # Создаем новых пользователей
                    if users_to_create:
                        try:
                            created = User.objects.bulk_create(
                                users_to_create,
                                batch_size=min(1000, len(users_to_create))
                            )
                            operation_log['successful'] += len(created)

                            # Получаем ID созданных пользователей
                            if created:
                                created_ids = [user.id for user in created]
                                operation_log['created_ids'].extend(created_ids)

                        except IntegrityError as e:
                            # Обработка других ошибок целостности
                            operation_log['failed'] += len(users_to_create)
                            operation_log['errors'].append({
                                'type': 'integrity_error',
                                'error': 'Нарушение уникальности при bulk_create',
                                'details': str(e)
                            })

                    # Обновляем существующих пользователей
                    if users_to_update:
                        try:
                            # Определяем, какие поля обновлять
                            update_fields = [
                                'first_name', 'last_name', 'description',
                                'is_public', 'is_active', 'updated_at'
                            ]

                            # Если у кого-то обновлен пароль, добавляем password_hash
                            password_updated = any('password' in users_to_update_dict[u.username]['data']
                                                   for u in users_to_update)
                            if password_updated:
                                update_fields.append('password_hash')

                            updated_count = User.objects.bulk_update(
                                users_to_update,
                                fields=update_fields
                            )
                            operation_log['successful'] += len(users_to_update)
                            operation_log['updated_ids'].extend([user.id for user in users_to_update])

                        except Exception as e:
                            operation_log['failed'] += len(users_to_update)
                            operation_log['errors'].append({
                                'type': 'update_error',
                                'error': str(e)
                            })

                operation_log['batches_processed'] += 1

        except Exception as e:
            # Критическая ошибка, не связанная с валидацией отдельных записей
            operation_log['errors'].append({
                'type': 'critical',
                'error': str(e)
            })
            operation_log['failed'] = operation_log['total_processed'] - operation_log['successful']

        # Сериализуем результат
        response_serializer = BatchOperationLogSerializer(operation_log)
        return Response(response_serializer.data)