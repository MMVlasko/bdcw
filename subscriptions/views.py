from django.db import connection, transaction, IntegrityError
from django.shortcuts import get_object_or_404
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from rest_framework import status, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import LimitOffsetPagination

from audit.models import BatchLog
from bdcw.authentication import TokenAuthentication, HasValidToken, IsAdmin
from bdcw.error_responses import (
    BAD_REQUEST_RESPONSE, UNAUTHORIZED_RESPONSE,
    FORBIDDEN_RESPONSE, NOT_FOUND_RESPONSE, INTERNAL_SERVER_ERROR, BAD_BATCH_REQUEST_RESPONSE
)
from core.models import User
from core.serializers import UserSerializer, BatchOperationLogSerializer
from .models import Subscription
from .serializers import SubscriptionSerializer, SubscriptionCreateSerializer, BatchSubscriptionCreateSerializer


class SubscriptionLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 10
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 100


class SubscriptionCreateView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken]

    @extend_schema(
        summary='Создать подписку',
        description='''
            Создание подписки

            Подписаться на другого пользователя.

            Права доступа:
            - Требуется действительный токен
            - Пользователь может подписаться только от своего имени
            - Администратор может создать подписку для любого пользователя

            Ограничения:
            - Нельзя подписаться на самого себя
            - Нельзя подписаться на пользователя с приватным профилем (если вы не администратор)
            - Нельзя создать дублирующую подписку
            ''',
        parameters=[
            OpenApiParameter(
                name='subscriber_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID подписчика (текущий пользователь или админ может указать другого)',
                required=True
            ),
            OpenApiParameter(
                name='subscribing_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID пользователя, на которого подписываются',
                required=True
            )
        ],
        responses={
            201: OpenApiResponse(
                response=SubscriptionSerializer,
                description='Created',
                examples=[
                    OpenApiExample(
                        name='Подписка успешно создана',
                        summary='Стандартный ответ при успешном создании',
                        value={
                            'subscriber': 123,
                            'subscribing': 456,
                            'subscribed_at': '2024-01-15T10:30:00Z'
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
        tags=['Подписки']
    )
    def post(self, request):
        subscriber_id = request.query_params.get('subscriber_id')
        subscribing_id = request.query_params.get('subscribing_id')

        if not subscriber_id or not subscribing_id:
            return Response(
                {'error': 'Необходимы параметры subscriber_id и subscribing_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            subscriber_id = int(subscriber_id)
            subscribing_id = int(subscribing_id)
        except (ValueError, TypeError):
            return Response(
                {'error': 'ID должны быть целыми числами'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if subscriber_id != request.user.id and request.user.role != User.UserRole.ADMIN:
            return Response(
                {'error': 'Нельзя подписать другого пользователя'},
                status=status.HTTP_403_FORBIDDEN
            )

        if subscribing_id == subscriber_id:
            return Response(
                {'error': 'Нельзя подписаться на самого себя'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            subscriber_user = User.objects.get(id=subscriber_id)
            subscribing_user = User.objects.get(id=subscribing_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Пользователь не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        existing_subscription = Subscription.objects.filter(
            subscriber=subscriber_user,
            subscribing=subscribing_user
        ).first()

        if existing_subscription:
            return Response(
                {'error': 'Подписка уже существует'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not subscribing_user.is_public and request.user.role != User.UserRole.ADMIN:
            return Response(
                {'error': 'Нельзя подписаться на пользователя с приватным профилем'},
                status=status.HTTP_403_FORBIDDEN
            )

        subscription_data = {
            'subscriber': subscriber_id,
            'subscribing': subscribing_id
        }

        serializer = SubscriptionCreateSerializer(data=subscription_data)
        serializer.is_valid(raise_exception=True)
        subscription = serializer.save()

        response_serializer = SubscriptionSerializer(subscription)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class SubscriptionDeleteView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken]

    @extend_schema(
        summary='Удалить подписку',
        description='''
            Удаление подписки

            Отписаться от пользователя.

            Права доступа:
            - Требуется действительный токен
            - Пользователь может отписаться только от своего имени
            - Администратор может удалить подписку для любого пользователя

            Процесс удаления:
            - Проверка существования обоих пользователей
            - Проверка существования подписки
            - Проверка прав доступа
            - Удаление записи подписки
            ''',
        parameters=[
            OpenApiParameter(
                name='subscriber_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID подписчика (текущий пользователь или админ может указать другого)',
                required=True
            ),
            OpenApiParameter(
                name='subscribing_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID пользователя, на которого отписываются',
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
        tags=['Подписки']
    )
    def delete(self, request):
        subscriber_id = request.query_params.get('subscriber_id')
        subscribing_id = request.query_params.get('subscribing_id')

        if not subscriber_id or not subscribing_id:
            return Response(
                {'error': 'Необходимы параметры subscriber_id и subscribing_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            subscriber_id = int(subscriber_id)
            subscribing_id = int(subscribing_id)
        except (ValueError, TypeError):
            return Response(
                {'error': 'ID должны быть целыми числами'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if subscriber_id != request.user.id and request.user.role != User.UserRole.ADMIN:
            return Response(
                {'error': 'Нельзя отписать другого пользователя'},
                status=status.HTTP_403_FORBIDDEN
            )

        if subscribing_id == subscriber_id:
            return Response(
                {'error': 'Нельзя подписаться на самого себя'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            subscriber_user = User.objects.get(id=subscriber_id)
            subscribing_user = User.objects.get(id=subscribing_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Пользователь не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        subscription = Subscription.objects.filter(
            subscriber=subscriber_user,
            subscribing=subscribing_user
        ).first()

        if not subscription:
            return Response(
                {'error': 'Подписка не существует'},
                status=status.HTTP_404_NOT_FOUND
            )

        subscription.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserSubscriptionsListView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken]
    pagination_class = SubscriptionLimitOffsetPagination

    @extend_schema(
        summary='Получить подписки пользователя',
        description='''
            Получение подписок пользователя

            Получить список пользователей, на которых подписан данный пользователь.

            Права доступа:
            - Требуется действительный токен
            - Пользователь может просматривать свои подписки
            - Администратор может просматривать подписки любого пользователя
            - Обычные пользователи могут просматривать подписки других пользователей только если их профиль публичный

            Особенности:
            - Возвращает только публичных пользователей для обычных пользователей
            - Администраторы видят всех пользователей, на которых подписан запрошенный пользователь

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            ''',
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID пользователя, чьи подписки запрашиваются'
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
                        name='Список подписок',
                        summary='Стандартный ответ со списком пользователей',
                        value={
                            'count': 15,
                            'next': 'http://127.0.0.1:8080/api/subscriptions/123/subscriptions/?limit=10&offset=10',
                            'previous': None,
                            'results': [
                                {
                                    'id': 456,
                                    'username': 'user456',
                                    'first_name': 'Иван',
                                    'last_name': 'Иванов',
                                    'description': 'Публичный профиль',
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
                        name='Пустой список подписок',
                        summary='Когда пользователь ни на кого не подписан',
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
        tags=['Подписки']
    )
    def get(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        current_user = request.user

        if current_user.id != user.id and current_user.role != User.UserRole.ADMIN:
            if not user.is_public:
                return Response(
                    {'error': 'Доступ к подпискам этого пользователя запрещен'},
                    status=status.HTTP_403_FORBIDDEN
                )

        subscription_user_ids = Subscription.objects.filter(
            subscriber=user_id
        ).values_list('subscribing_id', flat=True)

        subscriptions = User.objects.filter(id__in=subscription_user_ids)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(subscriptions, request)

        if page is not None:
            serializer = UserSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = UserSerializer(subscriptions, many=True)
        return Response(serializer.data)


class UserSubscribersListView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken]
    pagination_class = SubscriptionLimitOffsetPagination

    @extend_schema(
        summary='Получить подписчиков пользователя',
        description='''
            Получение подписчиков пользователя

            Получить список пользователей, которые подписаны на данного пользователя.

            Права доступа:
            - Требуется действительный токен
            - Пользователь может просматривать своих подписчиков
            - Администратор может просматривать подписчиков любого пользователя
            - Обычные пользователи могут просматривать подписчиков других пользователей только если их профиль публичный

            Особенности:
            - Возвращает только публичных пользователей для обычных пользователей
            - Администраторы видят всех пользователей, которые подписаны на запрошенного пользователя

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            ''',
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID пользователя, чьи подписчики запрашиваются'
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
                        name='Список подписчиков',
                        summary='Стандартный ответ со списком подписчиков',
                        value={
                            'count': 8,
                            'next': None,
                            'previous': None,
                            'results': [
                                {
                                    'id': 789,
                                    'username': 'user789',
                                    'first_name': 'Мария',
                                    'last_name': 'Петрова',
                                    'description': 'Публичный профиль',
                                    'role': 'user',
                                    'is_active': True,
                                    'is_public': True,
                                    'created_at': '2024-01-12T11:45:20Z',
                                    'updated_at': '2024-01-15T16:30:00Z'
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name='Пустой список подписчиков',
                        summary='Когда на пользователя никто не подписан',
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
        tags=['Подписки']
    )
    def get(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        current_user = request.user

        if current_user.id != user.id and current_user.role != User.UserRole.ADMIN:
            if not user.is_public:
                return Response(
                    {'error': 'Доступ к подписчикам этого пользователя запрещен'},
                    status=status.HTTP_403_FORBIDDEN
                )

        subscribing_user_ids = Subscription.objects.filter(
            subscribing=user_id
        ).values_list('subscriber_id', flat=True)

        subscriptions = User.objects.filter(id__in=subscribing_user_ids)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(subscriptions, request)

        if page is not None:
            serializer = UserSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = UserSerializer(subscriptions, many=True)
        return Response(serializer.data)


class CheckSubscriptionView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken]

    @extend_schema(
        summary='Проверить подписку',
        description='''
            Проверка подписки

            Проверить, подписан ли один пользователь на другого.

            Права доступа:
            - Требуется действительный токен
            - Пользователь может проверить только свои подписки
            - Администратор может проверить любую подписку

            Возвращаемые данные:
            - is_subscribed: Флаг наличия подписки (true/false)
            - subscribed_at: Дата и время создания подписки (только если подписка существует)

            Особенности:
            - Если подписка существует, возвращается информация о ней
            - Если подписка не существует, возвращается is_subscribed: false
            ''',
        parameters=[
            OpenApiParameter(
                name='subscriber_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID подписчика (текущий пользователь или админ может указать другого)',
                required=True
            ),
            OpenApiParameter(
                name='subscribing_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID пользователя, на которого проверяется подписка',
                required=True
            )
        ],
        responses={
            200: OpenApiResponse(
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Подписка существует',
                        summary='Пользователь подписан',
                        value={
                            'is_subscribed': True,
                            'subscribed_at': '2024-01-15T10:30:00Z'
                        }
                    ),
                    OpenApiExample(
                        name='Подписка не существует',
                        summary='Пользователь не подписан',
                        value={
                            'is_subscribed': False
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
        tags=['Подписки']
    )
    def get(self, request):
        subscriber_id = request.query_params.get('subscriber_id')
        subscribing_id = request.query_params.get('subscribing_id')

        if not subscriber_id or not subscribing_id:
            return Response(
                {'error': 'Необходимы параметры subscriber_id и subscribing_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            subscriber_id = int(subscriber_id)
            subscribing_id = int(subscribing_id)
        except (ValueError, TypeError):
            return Response(
                {'error': 'ID должны быть целыми числами'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if subscriber_id != request.user.id and request.user.role != User.UserRole.ADMIN:
            return Response(
                {'error': 'Нельзя проверить подписку другого'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            subscriber_user = User.objects.get(id=subscriber_id)
            subscribing_user = User.objects.get(id=subscribing_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Пользователь не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

        subscription = Subscription.objects.filter(
            subscriber=subscriber_user,
            subscribing=subscribing_user
        ).first()

        if subscription:
            return Response({
                'is_subscribed': True,
                'subscribed_at': subscription.subscribed_at
            })

        return Response({
            'is_subscribed': False
        })


class BatchSubscriptionCreateView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken, IsAdmin]

    @extend_schema(
        summary='Батчевая загрузка подписок',
        description='''
            Массовое создание подписок

            Создание нескольких подписок за одну операцию с использованием bulk_create.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут создавать подписки батчами

            Обязательные поля для каждой подписки:
            - subscriber_id: ID подписчика
            - subscribing_id: ID пользователя, на которого подписываются

            Ограничения:
            - Максимум 10,000 подписок за запрос
            - batch_size от 1 до 5,000
            - subscriber_id и subscribing_id должны быть разными
            - Оба пользователя должны существовать в системе
            - Нельзя создавать дублирующие подписки
            ''',
        request=BatchSubscriptionCreateSerializer,
        responses={
            200: OpenApiResponse(
                response=BatchOperationLogSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Полностью успешная операция',
                        summary='Все подписки созданы',
                        value={
                            'total_processed': 50,
                            'successful': 50,
                            'failed': 0,
                            'batch_size': 25,
                            'errors': [],
                            'created_ids': [123, 456, 789, 101],
                            'batches_processed': 2
                        }
                    ),
                    OpenApiExample(
                        name='Операция с ошибками',
                        summary='Некоторые подписки не созданы',
                        value={
                            'total_processed': 5,
                            'successful': 3,
                            'failed': 2,
                            'batch_size': 100,
                            'errors': [
                                {
                                    'ata': {
                                        'subscriber_id': 123,
                                        'subscribing_id': 456
                                    },
                                    'error': 'Подписка пользователя 123 на пользователя 456 уже существует',
                                    'type': 'duplicate_error'
                                },
                                {
                                    'data': {
                                        'subscriber_id': 999,
                                        'subscribing_id': 888
                                    },
                                    'error': 'Пользователь-подписчик с ID 999 не существует',
                                    'type': 'validation_error'
                                }
                            ],
                            'created_ids': [111, 222, 333],
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
                name='Пример создания подписок',
                value={
                    'subscriptions': [
                        {
                            'subscriber_id': 1,
                            'subscribing_id': 2
                        },
                        {
                            'subscriber_id': 1,
                            'subscribing_id': 3
                        },
                        {
                            'subscriber_id': 2,
                            'subscribing_id': 1
                        }
                    ],
                    'batch_size': 100
                },
                request_only=True
            )
        ],
        tags=['Подписки']
    )
    def post(self, request):
        serializer = BatchSubscriptionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Ошибка валидации',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        subscriptions_data = serializer.validated_data['subscriptions']
        batch_size = serializer.validated_data['batch_size']

        operation_log = {
            'total_processed': len(subscriptions_data),
            'successful': 0,
            'failed': 0,
            'errors': [],
            'created_ids': [],
            'batches_processed': 0,
            'batch_size': batch_size
        }

        try:
            validated_subscriptions_data = []

            all_user_ids = set()
            for subscription_data in subscriptions_data:
                all_user_ids.add(subscription_data.get('subscriber_id'))
                all_user_ids.add(subscription_data.get('subscribing_id'))

            all_user_ids = {uid for uid in all_user_ids if uid is not None}

            existing_users = User.objects.filter(id__in=all_user_ids)
            existing_user_ids = set(user.id for user in existing_users)

            for i, subscription_data in enumerate(subscriptions_data):
                try:
                    processed_data = subscription_data.copy()

                    required_fields = ['subscriber_id', 'subscribing_id']
                    missing_fields = []

                    for field in required_fields:
                        if field not in processed_data:
                            missing_fields.append(field)

                    if missing_fields:
                        raise ValueError(f'Обязательные поля отсутствуют: {", ".join(missing_fields)}')

                    subscriber_id = processed_data['subscriber_id']
                    subscribing_id = processed_data['subscribing_id']

                    if isinstance(subscriber_id, str):
                        try:
                            processed_data['subscriber_id'] = int(subscriber_id)
                        except ValueError:
                            raise ValueError(f'subscriber_id должен быть целым числом, получено: {subscriber_id}')
                    elif not isinstance(subscriber_id, int):
                        raise ValueError(f'subscriber_id должен быть целым числом, получено: {subscriber_id}')

                    if isinstance(subscribing_id, str):
                        try:
                            processed_data['subscribing_id'] = int(subscribing_id)
                        except ValueError:
                            raise ValueError(f'subscribing_id должен быть целым числом, получено: {subscribing_id}')
                    elif not isinstance(subscribing_id, int):
                        raise ValueError(f'subscribing_id должен быть целым числом, получено: {subscribing_id}')

                    if processed_data['subscriber_id'] == processed_data['subscribing_id']:
                        raise ValueError(
                            f'Пользователь не может подписаться на самого себя. '
                            f'subscriber_id={subscriber_id}, subscribing_id={subscribing_id}'
                        )

                    if processed_data['subscriber_id'] not in existing_user_ids:
                        raise ValueError(f'Пользователь-подписчик с ID {processed_data["subscriber_id"]} не существует')

                    if processed_data['subscribing_id'] not in existing_user_ids:
                        raise ValueError(
                            f'Пользователь, на которого подписываются, с '
                            f'ID {processed_data["subscribing_id"]} не существует')

                    validated_subscriptions_data.append({
                        'index': i,
                        'data': processed_data,
                        'subscriber_id': processed_data['subscriber_id'],
                        'subscribing_id': processed_data['subscribing_id']
                    })

                except serializers.ValidationError as e:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': subscription_data,
                        'error': e.detail,
                        'type': 'validation_error'
                    })
                except Exception as e:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': subscription_data,
                        'error': str(e),
                        'type': 'validation_error'
                    })

            if not validated_subscriptions_data:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            subscription_keys = set()
            for item in validated_subscriptions_data:
                key = (item['subscriber_id'], item['subscribing_id'])
                subscription_keys.add(key)

            existing_subscriptions_set = set()

            if subscription_keys:
                q_objects = Q()
                for subscriber_id, subscribing_id in subscription_keys:
                    q_objects |= Q(subscriber_id=subscriber_id, subscribing_id=subscribing_id)

                existing_subscriptions = Subscription.objects.filter(q_objects)
                for sub in existing_subscriptions:
                    existing_subscriptions_set.add((sub.subscriber_id, sub.subscribing_id))

            filtered_subscriptions_data = []
            for item in validated_subscriptions_data:
                subscriber_id = item['subscriber_id']
                subscribing_id = item['subscribing_id']
                key = (subscriber_id, subscribing_id)

                if key in existing_subscriptions_set:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': item['data'],
                        'error': f'Подписка пользователя {subscriber_id} на '
                                 f'пользователя {subscribing_id} уже существует',
                        'type': 'duplicate_error'
                    })
                else:
                    filtered_subscriptions_data.append(item)

            if not filtered_subscriptions_data:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            user_ids_set = set()
            for item in filtered_subscriptions_data:
                data = item['data']
                user_ids_set.add(data['subscriber_id'])
                user_ids_set.add(data['subscribing_id'])

            users_dict = {user.id: user for user in User.objects.filter(id__in=user_ids_set)}

            missing_users = user_ids_set - set(users_dict.keys())
            if missing_users:
                for item in filtered_subscriptions_data:
                    data = item['data']
                    if data['subscriber_id'] in missing_users or data['subscribing_id'] in missing_users:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'data': data,
                            'error': f'Один из пользователей не существует: '
                                     f'subscriber_id={data["subscriber_id"]}, subscribing_id={data["subscribing_id"]}',
                            'type': 'reference_error'
                        })
                filtered_subscriptions_data = [
                    item for item in filtered_subscriptions_data
                    if item['data']['subscriber_id'] not in missing_users and
                    item['data']['subscribing_id'] not in missing_users
                ]

            if not filtered_subscriptions_data:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            batches = [
                filtered_subscriptions_data[i:i + batch_size]
                for i in range(0, len(filtered_subscriptions_data), batch_size)
            ]

            for batch_index, batch in enumerate(batches):
                subscriptions_to_create = []

                for item in batch:
                    subscription_data = item['data']

                    try:
                        subscriber = users_dict[subscription_data['subscriber_id']]
                        subscribing = users_dict[subscription_data['subscribing_id']]

                        subscription = Subscription(
                            subscriber=subscriber,
                            subscribing=subscribing
                        )

                        subscriptions_to_create.append(subscription)
                    except KeyError as e:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'data': subscription_data,
                            'error': f'Ошибка при создании подписки: {str(e)}',
                            'type': 'creation_error'
                        })
                    except Exception as e:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'data': subscription_data,
                            'error': f'Ошибка при создании подписки: {str(e)}',
                            'type': 'creation_error'
                        })

                with connection.cursor() as cursor:
                    cursor.execute('ALTER TABLE subscriptions DISABLE TRIGGER audit_subscriptions_trigger')

                try:
                    with transaction.atomic():
                        if subscriptions_to_create:
                            try:
                                created = Subscription.objects.bulk_create(
                                    subscriptions_to_create,
                                    batch_size=len(subscriptions_to_create)
                                )
                                operation_log['successful'] += len(created)

                                for subscription in created:
                                    operation_log['created_ids'].append(subscription.subscriber_id)
                                    operation_log['created_ids'].append(subscription.subscribing_id)

                            except IntegrityError as e:
                                operation_log['failed'] += len(subscriptions_to_create)
                                operation_log['errors'].append({
                                    'type': 'integrity_error',
                                    'error': 'Ошибка целостности при bulk_create подписок',
                                    'details': str(e)
                                })
                                raise
                            except Exception as e:
                                operation_log['failed'] += len(subscriptions_to_create)
                                operation_log['errors'].append({
                                    'type': 'bulk_create_error',
                                    'error': str(e)
                                })

                finally:
                    # Включаем триггер обратно
                    with connection.cursor() as cursor:
                        cursor.execute('ALTER TABLE subscriptions ENABLE TRIGGER audit_subscriptions_trigger')

                operation_log['batches_processed'] += 1

        except Exception as e:
            operation_log['errors'].append({
                'type': 'critical',
                'error': str(e)
            })
            operation_log['failed'] = operation_log['total_processed'] - operation_log['successful']

        batch_log = BatchLog(
            table_name='subscriptions',
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
