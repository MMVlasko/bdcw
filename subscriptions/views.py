from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import LimitOffsetPagination

from bdcw.authentication import TokenAuthentication, HasValidToken
from bdcw.error_responses import (
    BAD_REQUEST_RESPONSE, UNAUTHORIZED_RESPONSE,
    FORBIDDEN_RESPONSE, NOT_FOUND_RESPONSE, INTERNAL_SERVER_ERROR
)
from core.models import User
from core.serializers import UserSerializer
from .models import Subscription
from .serializers import SubscriptionSerializer, SubscriptionCreateSerializer


class SubscriptionLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 10
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 100


class SubscriptionCreateView(APIView):
    """
    Создание подписки
    POST /api/subscriptions/?subscriber_id=1&subscribing_id=2
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken]

    @extend_schema(
        summary="Создать подписку",
        description="Подписаться на другого пользователя",
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
            201: SubscriptionSerializer,
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
    """
    Удаление подписки
    DELETE /api/subscriptions/{user_id}/
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken]

    @extend_schema(
        summary="Удалить подписку",
        description="Отписаться от пользователя",
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
            204: None,
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
        summary="Получить подписки пользователя",
        description="Получить список пользователей, на которых подписан данный пользователь",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID пользователя'
            )
        ],
        responses={
            200: UserSerializer(many=True),
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
        summary="Получить подписчиков пользователя",
        description="Получить список пользователей, которые подписаны на данного пользоваеля",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID пользователя'
            )
        ],
        responses={
            200: UserSerializer(many=True),
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
        summary="Проверить подписку",
        description="Проверить, подписан ли один пользователь на другого",
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
            201: {
                'type': 'object',
                'properties': {
                    'is_subscribed': {'type': 'boolean'},
                    'subscribed_at': {'type': 'string', 'format': 'date-time'}
                }
            },
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