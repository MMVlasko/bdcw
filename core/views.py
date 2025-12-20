from django.db import transaction, IntegrityError, connection
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter, OpenApiResponse
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import BatchLog
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
        summary='Получить список пользователей',
        description='''
            Получение списка пользователей

            Возвращает список пользователей с пагинацией.

            Особенности:
            - Администраторы видят всех пользователей
            - Обычные пользователи** видят только пользователей с is_public=True
            - Результаты упорядочены по дате создания (новые первыми)

            Права доступа:
            - Требуется действительный токен
            - Аутентификация: TokenAuthentication

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            ''',
        parameters=[
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Количество записей на странице (макс. 100)',
                required=False,
                default=10,
                examples=[
                    OpenApiExample('Минимум', value=1),
                    OpenApiExample('По умолчанию', value=10),
                    OpenApiExample('Максимум', value=100),
                ]
            ),
            OpenApiParameter(
                name='offset',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Смещение от начала списка',
                required=False,
                default=0,
                examples=[
                    OpenApiExample('Начало', value=0),
                    OpenApiExample('Страница 2 при limit=10', value=10),
                ]
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=UserSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Пустой список',
                        summary='Когда пользователей нет или недоступны',
                        value={
                            'count': 0,
                            'next': None,
                            'previous': None,
                            'results': []
                        },
                        description='Пользователей не найдено или у вас нет доступа'
                    ),
                    OpenApiExample(
                        name='Список пользователей (администратор)',
                        summary='Полный список для администратора',
                        value={
                            'ount': 502,
                            'next': 'http://127.0.0.1:8080/api/users/?limit=2&offset=2',
                            'previous': None,
                            'results': [
                                {
                                    'id': 581,
                                    'username': 'srdthjri',
                                    'first_name': 'reyt',
                                    'last_name': 'fhdf',
                                    'description': None,
                                    'role': 'user',
                                    'is_active': True,
                                    'is_public': True,
                                    'created_at': '2025-12-18T00:33:52.606000+03:00',
                                    'updated_at': '2025-12-18T00:33:54.468000+03:00'
                                },
                                {
                                    'id': 582,
                                    'username': 'avdeevagalina2057',
                                    'first_name': 'Ульяна',
                                    'last_name': 'Петрова',
                                    'description': None,
                                    'role': 'user',
                                    'is_active': True,
                                    'is_public': True,
                                    'created_at': '2025-12-18T13:19:36.784614+03:00',
                                    'updated_at': '2025-12-18T13:19:36.784640+03:00'
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name='Список пользователей (обычный пользователь)',
                        summary='Только публичные пользователи',
                        value={
                            'count': 150,
                            'next': 'http://127.0.0.1:8080/api/users/?limit=2&offset=2',
                            'previous': None,
                            'results': [
                                {
                                    'id': 581,
                                    'username': 'public_user1',
                                    'first_name': 'Иван',
                                    'last_name': 'Петров',
                                    'description': 'Публичный профиль',
                                    'role': 'user',
                                    'is_active': True,
                                    'is_public': True,
                                    'created_at': '2025-12-18T00:33:52.606000+03:00',
                                    'updated_at': '2025-12-18T00:33:54.468000+03:00'
                                }
                            ]
                        },
                        description='Обычные пользователи видят только пользователей с is_public=True'
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Пользователи']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary='Создать нового пользователя',
        description='''
            Регистрация нового пользователя

            Создает нового пользователя в системе. Эндпоинт не требует аутентификации.

            Обязательные поля:
            - username: Уникальное имя пользователя (мин. 3 символа, только буквы, цифры и подчеркивания)
            - password: Пароль (мин. 8 символов, должен содержать цифры и заглавные буквы)
            - confirm_password: Подтверждение пароля (должен совпадать с password)
            - first_name: Имя пользователя
            - last_name: Фамилия пользователя

            Опциональные поля:
            - description: Описание пользователя
            - is_public: Видимость профиля (по умолчанию: True)

            Автоматически устанавливается:
            - role: user (по умолчанию)
            - is_active: True
            - created_at: Текущее время
            - updated_at: Текущее время

            Валидация:
            - Проверка уникальности username
            - Проверка формата username
            - Проверка сложности пароля
            - Проверка совпадения password и confirm_password
            ''',
        request=UserCreateSerializer,
        responses={
            201: OpenApiResponse(
                response=UserSerializer,
                description='Created',
                examples=[
                    OpenApiExample(
                        name='Пользователь успешно создан',
                        summary='Стандартный ответ при успешном создании',
                        value={
                            'id': 789,
                            'username': 'john_doe',
                            'first_name': 'John',
                            'last_name': 'Doe',
                            'description': 'Разработчик из Москвы',
                            'role': 'user',
                            'is_active': True,
                            'is_public': True,
                            'created_at': '2024-01-15T10:30:00Z',
                            'updated_at': '2024-01-15T10:30:00Z'
                        }
                    )
                ]
            ),
            400: BAD_REQUEST_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        examples=[
            OpenApiExample(
                name='Пример создания пользователя',
                value={
                    'username': 'john_doe',
                    'password': 'SecurePass123',
                    'confirm_password': 'SecurePass123',
                    'first_name': 'John',
                    'last_name': 'Doe',
                    'description': 'Разработчик из Москвы',
                    'is_public': True
                },
                request_only=True
            )
        ],
        tags=['Пользователи']
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary='Получить информацию о пользователе',
        description='''
            Получение детальной информации о пользователе

            Возвращает полную информацию о конкретном пользователе по его ID.

            Права доступа:
            - Требуется действительный токен
            - Любой аутентифицированный пользователь может видеть:
              * Себя (любую информацию)
              * Других пользователей с is_public=True
            - Администраторы могут видеть всех пользователей

            Возвращаемые поля:
            - id: Идентификатор пользователя
            - username: Имя пользователя
            - first_name: Имя
            - last_name: Фамилия
            - description: Описание
            - role: Роль (user или admin)
            - is_active: Активен ли пользователь
            - is_public: Виден ли профиль публично
            - created_at: Дата создания
            - updated_at: Дата обновления
            ''',
        responses={
            200: OpenApiResponse(
                response=UserSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Активный публичный пользователь',
                        summary='Стандартный профиль пользователя',
                        value={
                            'id': 123,
                            'username': 'ivan_ivanov',
                            'first_name': 'Иван',
                            'last_name': 'Иванов',
                            'description': 'Бэкенд разработчик',
                            'role': 'user',
                            'is_active': True,
                            'is_public': True,
                            'created_at': '2024-01-10T09:15:30Z',
                            'updated_at': '2024-01-15T14:20:45Z'
                        }
                    ),
                    OpenApiExample(
                        name='Пользователь-администратор',
                        summary='Профиль администратора',
                        value={
                            'id': 1,
                            'username': 'admin',
                            'first_name': 'Алексей',
                            'last_name': 'Петров',
                            'description': 'Системный администратор',
                            'role': 'admin',
                            'is_active': True,
                            'is_public': False,
                            'created_at': '2024-01-01T00:00:00Z',
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
        tags=['Пользователи']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary='Полное обновление пользователя',
        description='''
            Полное обновление информации пользователя

            Заменяет все данные пользователя новыми значениями. Все поля обязательны.

            Права доступа:
            - Требуется действительный токен
            - Пользователь может обновлять только свой профиль
            - Администратор может обновлять любой профиль

            Обязательные поля:
            - username: Имя пользователя (должно быть уникальным)
            - first_name: Имя
            - last_name: Фамилия
            - description: Описание (может быть null)
            - is_active: Активен ли пользователь
            - is_public: Виден ли профиль публично

            Валидация:
            - Проверка уникальности username (если изменен)
            - Проверка формата username
            - Проверка обязательных полей

            Примечание:
            - Пароль изменяется через отдельный эндпоинт change_password
            - Роль изменяется через отдельный эндпоинт change_role
            ''',
        request=UserUpdateSerializer,
        responses={
            200: OpenApiResponse(
                response=UserSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Пользователь успешно обновлен',
                        summary='Стандартный ответ при успешном обновлении',
                        value={
                            'id': 123,
                            'username': 'new_username',
                            'first_name': 'НовоеИмя',
                            'last_name': 'НоваяФамилия',
                            'description': 'Обновленное описание',
                            'role': 'user',
                            'is_active': True,
                            'is_public': False,
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
        examples=[
            OpenApiExample(
                name='Пример полного обновления',
                value={
                    'username': 'ivanov_ivan',
                    'first_name': 'Иван',
                    'last_name': 'Иванов',
                    'description': 'Обновленное описание профиля',
                    'is_active': True,
                    'is_public': True
                },
                request_only=True
            )
        ],
        tags=['Пользователи']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary='Частичное обновление пользователя',
        description='''
            Частичное обновление информации пользователя

            Обновляет только указанные поля пользователя. Не указанные поля остаются без изменений.

            Права доступа:
            - Требуется действительный токен
            - Пользователь может обновлять только свой профиль
            - Администратор может обновлять любой профиль

            Доступные для обновления поля:
            - username: Имя пользователя (с валидацией)
            - first_name: Имя
            - last_name: Фамилия
            - description: Описание (можно установить в null)
            - is_active: Активен ли пользователь (только для администраторов)
            - is_public: Виден ли профиль публично

            Ограничения:
            - Нельзя изменить роль (используйте change_role)
            - Нельзя изменить пароль (используйте change_password)
            ''',
        request=UserPartialUpdateSerializer,
        responses={
            200: OpenApiResponse(
                response=UserSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Обновление описания',
                        summary='Обновлено только описание',
                        value={
                            'id': 123,
                            'username': 'ivanov',
                            'first_name': 'Иван',
                            'last_name': 'Иванов',
                            'description': 'Новое описание профиля',
                            'role': 'user',
                            'is_active': True,
                            'is_public': True,
                            'created_at': '2024-01-10T09:15:30Z',
                            'updated_at': '2024-01-15T15:45:00Z'
                        }
                    ),
                    OpenApiExample(
                        name='Обновление имени и публичности',
                        summary='Обновлено несколько полей',
                        value={
                            'id': 456,
                            'username': 'petrov',
                            'first_name': 'Петр',
                            'last_name': 'Петров',
                            'escription': 'Старое описание',
                            'role': 'user',
                            'is_active': True,
                            'is_public': True,
                            'created_at': '2024-01-05T11:45:20Z',
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
        examples=[
            OpenApiExample(
                name='Обновить только описание',
                value={
                    'description': 'Новое описание моего профиля'
                },
                request_only=True
            ),
            OpenApiExample(
                name='Обновить имя и публичность',
                value={
                    'first_name': 'Александр',
                    'is_public': False
                },
                request_only=True
            )
        ],
        tags=['Пользователи']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary='Удалить пользователя',
        description='''
            Удаление пользователя из системы

            Полностью удаляет пользователя и все связанные данные из системы.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут удалять пользователей
            - Пользователи не могут удалять себя или других

            Последствия удаления:
            - Безвозвратное удаление пользователя
            - Каскадное удаление связанных записей
            - Освобождение username для повторного использования
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
        tags=['Пользователи']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary='Изменить пароль пользователя',
        description='''
            Смена пароля пользователя

            Позволяет пользователю изменить свой пароль или администратору изменить пароль другого пользователя.

            Права доступа:
            - Требуется действительный токен
            - Пользователь может изменить только свой пароль
            - Администратор может изменить пароль любого пользователя

            Требования к паролю:
            - Длина: Не менее 8 символов
            - Сложность:
              * Минимум одна цифра
              * Минимум одна заглавная буква
              * Минимум одна строчная буква
            - Подтверждение: password и confirm_password должны совпадать

            Процесс смены:
            - Валидация нового пароля
            - Хэширование с помощью bcrypt
            - Обновление password_hash в базе данных
            - Не влияет на активные сессии (токены продолжают работать)
            ''',
        request=UserChangePasswordSerializer,
        responses={
            200: OpenApiResponse(
                description='OK'
            ),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        examples=[
            OpenApiExample(
                name='Пример смены пароля',
                value={
                    'password': 'NewSecurePass123',
                    'confirm_password': 'NewSecurePass123'
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

    @extend_schema(
        summary='Изменить роль пользователя',
        description='''
            Изменение роли пользователя

            Позволяет администраторам изменять роль пользователя между user и admin.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут изменять роли

            Доступные роли:
            - user: Обычный пользователь
              * Может просматривать публичные профили
              * Может редактировать свой профиль
            - admin: Администратор
              * Полный доступ ко всем пользователям
              * Может изменять роли
              * Может удалять пользователей

            Ограничения:
            - Роль должна быть либо 'admin', либо 'user'

            Влияние на права:
            - Изменение роли применяется немедленно
            - Активные токены сохраняют свои права
            - Новые права применяются к новым сессиям
            ''',
        request=None,
        parameters=[
            OpenApiParameter(
                name='role',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Новая роль пользователя (admin или user)',
                required=True,
                enum=['admin', 'user'],
                examples=[
                    OpenApiExample('Повышение до админа', value='admin'),
                    OpenApiExample('Понижение до пользователя', value='user')
                ]
            ),
        ],
        responses={
            200: OpenApiResponse(
                description='OK'
            ),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Пользователи']
    )
    @action(['put'], detail=True)
    def change_role(self, request, pk=None):
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
        summary='Вход в систему',
        description='''
            Аутентификация пользователя

            Получение токена доступа для работы с API.

            Процесс аутентификации:
            - Проверка учетных данных:
              * Существование пользователя
              * Корректность пароля
              * Активность учетной записи
            - Создание токена:
              * Генерация уникального токена
              * Установка времени жизни (24 часа)
              * Привязка к пользователю
              * Обновление last_login

            Требования к учетным данным:
            - username: Существующий username в системе
            - password: Пароль, соответствующий хэшу в базе

            Ответ содержит:
            - success: Статус операции
            - token: Токен для авторизации
            - expires_at: Время истечения токена
            - user: Данные аутентифицированного пользователя
            ''',
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(
                response=LoginResponseSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Успешный вход',
                        summary='Стандартный успешный ответ',
                        value={
                            'success': True,
                            'message': 'Авторизация успешна',
                            'token': 'a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef',
                            'expires_at': '2024-01-16T10:30:00Z',
                            'user': {
                                'id': 123,
                                'username': 'john_doe',
                                'first_name': 'John',
                                'ast_name': 'Doe',
                                'description': 'Разработчик',
                                'role': 'user',
                                'is_active': True,
                                'is_public': True,
                                'created_at': '2024-01-10T09:15:30Z',
                                'updated_at': '2024-01-15T14:20:45Z'
                            }
                        }
                    )
                ]
            ),
            400: BAD_REQUEST_RESPONSE,
            401: UNAUTHORIZED_RESPONSE
        },
        examples=[
            OpenApiExample(
                name='Пример входа',
                value={
                    'username': 'john_doe',
                    'password': 'SecurePass123'
                },
                request_only=True
            )
        ],
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
        summary='Выход из системы',
        description='''
            Завершение сессии пользователя

            Деактивирует текущий токен авторизации, делая его недействительным для последующих запросов.

            Процесс выхода:
            - Идентификация токена из заголовка Authorization
            - Деактивация: Установка is_active=false
            - Сохранение: Обновление записи в базе данных

            Особенности:
            - Деактивируется только текущий токен
            - Другие активные токены пользователя остаются действительными
            - Токен помечается как неактивный, но не удаляется
            - Для полной очистки используйте /auth/clean-tokens/
            ''',
        responses={
            200: OpenApiResponse(
                description='OK'
            ),
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
        summary='Очистка деактивированных токенов авторизации',
        description='''
            Административная очистка токенов

            Полностью удаляет все деактивированные (неактивные) токены авторизации из базы данных.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут выполнять очистку

            Что удаляется:
            - Все токены с is_active=false
            ''',
        responses={
            204: OpenApiResponse(
                description='No Content'
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            500: INTERNAL_SERVER_ERROR
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
        summary='Батчевая загрузка пользователей',
        description='''
            Массовое создание пользователей

            Создание множества пользователей за одну операцию с использованием оптимизированных bulk операций.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут создавать пользователей батчами

            Обязательные поля для каждого пользователя:
            - username: Уникальное имя пользователя
            - password: Пароль
            - confirm_password: Подтверждение пароля (должен совпадать с password)
            - first_name: Имя
            - last_name: Фамилия
            - role: Роль (user или admin)

            Опциональные поля:
            - description: Описание пользователя
            - is_public: Видимость профиля (по умолчанию: true)
            - is_active: Активность учетной записи (по умолчанию: true)

            Ограничения:
            - Максимум 10,000 пользователей за запрос
            - batch_size от 1 до 5,000
            - Все username должны быть уникальными
            - Нельзя создавать существующих пользователей
            ''',
        request=BatchUserCreateSerializer,
        responses={
            200: OpenApiResponse(
                response=BatchOperationLogSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Полностью успешная операция',
                        summary='Все пользователи созданы',
                        value={
                            'total_processed': 100,
                            'successful': 100,
                            'failed': 0,
                            'batch_size': 50,
                            'errors': [],
                            'created_ids': [1001, 1002, 1003, 1004, 1005],
                            'batches_processed': 2
                        }
                    ),
                    OpenApiExample(
                        name='Операция с ошибками',
                        summary='Некоторые пользователи не созданы',
                        value={
                            'total_processed': 4,
                            'successful': 3,
                            'failed': 1,
                            'batch_size': 4,
                            'errors': [
                                {
                                    'data': {
                                        'username': 'existing_user',
                                        'password': 'pass123',
                                        'confirm_password': 'pass123',
                                        'first_name': 'Иван',
                                        'last_name': 'Иванов',
                                        'role': 'user'
                                    },
                                    'username': 'existing_user',
                                    'error': 'Пользователь с username existing_user уже существует',
                                    'type': 'duplicate_error'
                                }
                            ],
                            'created_ids': [1006, 1007, 1008],
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
        examples=[
            OpenApiExample(
                name='Создание 3 пользователей',
                value={
                    'users': [
                        {
                            'username': 'user001',
                            'password': 'Pass123456',
                            'confirm_password': 'Pass123456',
                            'first_name': 'Иван',
                            'last_name': 'Иванов',
                            'role': 'user',
                            'description': 'Первый тестовый пользователь',
                            'is_public': True,
                            'is_active': True
                        },
                        {
                            'username': 'user002',
                            'password': 'Pass123456',
                            'confirm_password': 'Pass123456',
                            'first_name': 'Мария',
                            'last_name': 'Петрова',
                            'role': 'user',
                            'is_public': False,
                            'is_active': True
                        }
                    ],
                    'batch_size': 2
                },
                request_only=True
            )
        ],
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

        operation_log = {
            'total_processed': len(users_data),
            'successful': 0,
            'failed': 0,
            'errors': [],
            'created_ids': [],
            'batches_processed': 0,
            'batch_size': batch_size
        }

        try:
            validated_users_data = []
            usernames_in_request = set()

            for i, user_data in enumerate(users_data):
                try:
                    username = user_data.get('username', '')

                    if username in usernames_in_request:
                        raise ValueError(f'Username {username} дублируется в этом запросе')
                    usernames_in_request.add(username)

                    validate_username(username)

                    required_fields = ['password', 'confirm_password', 'first_name', 'last_name', 'role']
                    for field in required_fields:
                        if field not in user_data:
                            raise ValueError(f'Обязательное поле {field} отсутствует')

                    if user_data['password'] != user_data['confirm_password']:
                        raise ValueError('Пароли не совпадают')

                    validate_password(user_data['password'], user_data['confirm_password'])

                    validated_users_data.append({
                        'index': i,
                        'data': user_data,
                        'username': username
                    })

                except (serializers.ValidationError, ValueError) as e:
                    operation_log['failed'] += 1
                    error_detail = e.detail if hasattr(e, 'detail') else str(e)
                    operation_log['errors'].append({
                        'data': user_data,
                        'username': user_data.get('username', 'unknown'),
                        'error': error_detail,
                        'type': 'validation_error'
                    })
                except Exception as e:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': user_data,
                        'username': user_data.get('username', 'unknown'),
                        'error': str(e),
                        'type': 'validation_error'
                    })

            if not validated_users_data:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            # Проверка существующих пользователей в базе данных
            usernames = [item['username'] for item in validated_users_data]
            existing_qs = User.objects.filter(username__in=usernames)
            existing_usernames = set(user.username for user in existing_qs)

            filtered_users = []

            for item in validated_users_data:
                username = item['username']
                user_data = item['data']

                if username in existing_usernames:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': user_data,
                        'username': username,
                        'error': f'Пользователь с username {username} уже существует',
                        'type': 'duplicate_error'
                    })
                else:
                    filtered_users.append(item)

            if not filtered_users:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            batches = [
                filtered_users[i:i + batch_size]
                for i in range(0, len(filtered_users), batch_size)
            ]

            for batch_index, batch in enumerate(batches):
                users_to_create = []

                for item in batch:
                    username = item['username']
                    user_data = item['data']

                    try:
                        user = User(
                            username=username,
                            first_name=user_data['first_name'],
                            last_name=user_data['last_name'],
                            role=user_data['role'],
                            description=user_data.get('description'),
                            is_public=user_data.get('is_public', True),
                            is_active=user_data.get('is_active', True),
                            created_at=timezone.now(),
                            updated_at=timezone.now()
                        )

                        user.set_password(user_data['password'])
                        users_to_create.append(user)

                    except Exception as e:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'data': user_data,
                            'username': username,
                            'error': str(e),
                            'type': 'creation_error'
                        })

                with connection.cursor() as cursor:
                    cursor.execute(f'ALTER TABLE users DISABLE TRIGGER audit_users_trigger')

                try:
                    with transaction.atomic():
                        if users_to_create:
                            try:
                                created = User.objects.bulk_create(
                                    users_to_create,
                                    batch_size=len(users_to_create)
                                )
                                operation_log['successful'] += len(created)

                                if created:
                                    created_ids = [user.id for user in created]
                                    operation_log['created_ids'].extend(created_ids)

                            except IntegrityError as e:
                                operation_log['failed'] += len(users_to_create)
                                operation_log['errors'].append({
                                    'type': 'integrity_error',
                                    'error': 'Нарушение уникальности при bulk_create',
                                    'details': str(e)
                                })
                                raise

                finally:
                    with connection.cursor() as cursor:
                        cursor.execute(f'ALTER TABLE users ENABLE TRIGGER audit_users_trigger')

                operation_log['batches_processed'] += 1

        except Exception as e:
            operation_log['errors'].append({
                'type': 'critical',
                'error': str(e)
            })
            operation_log['failed'] = operation_log['total_processed'] - operation_log['successful']

        batch_log = BatchLog(
            table_name='users',
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
