from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import LimitOffsetPagination

from bdcw.authentication import TokenAuthentication, HasValidToken, IsAdmin
from bdcw.error_responses import (
    UNAUTHORIZED_RESPONSE,
    FORBIDDEN_RESPONSE, NOT_FOUND_RESPONSE, INTERNAL_SERVER_ERROR
)

from .models import AuditLog, BatchLog
from .serializers import AuditLogSerializer, BatchLogSerializer


class AuditLogLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 10
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 100


class AuditLogDeleteView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken, IsAdmin]

    @extend_schema(
        summary="Удалить запись журнала аудита",
        description="""
            Удаление записи журнала аудита

            Полностью удаляет запись аудита по её ID.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут удалять записи аудита
            """,
        parameters=[
            OpenApiParameter(
                name='log_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID записи аудита для удаления',
                required=True
            )
        ],
        responses={
            204: OpenApiResponse(
                description='No Content'
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Журнал аудита']
    )
    def delete(self, request, log_id=None):
        try:
            log = AuditLog.objects.get(id=log_id)
        except AuditLog.DoesNotExist:
            return Response(
                {'error': 'Запись не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

        log.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuditLogListView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken, IsAdmin]
    pagination_class = AuditLogLimitOffsetPagination

    @extend_schema(
        summary="Получить записи журнала аудита",
        description="""
            Получение записей журнала аудита

            Возвращает список всех записей аудита с пагинацией.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут просматривать записи аудита

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка

            Возвращаемые поля:
            - id: Идентификатор записи
            - table_name: Имя таблицы, в которой произошли изменения
            - record_id: ID записи в таблице
            - operation: Тип операции (INSERT, UPDATE, DELETE)
            - old_values: Предыдущие значения (для UPDATE и DELETE)
            - new_values: Новые значения (для INSERT и UPDATE)
            - changed_by: Пользователь, выполнивший изменение
            - changed_at: Дата и время изменения
            """,
        parameters=[
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
                response=AuditLogSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Список записей аудита",
                        summary="Стандартный ответ со списком записей",
                        value={
                            "count": 150,
                            "next": "http://127.0.0.1:8080/api/audit-logs/?limit=10&offset=10",
                            "previous": None,
                            "results": [
                                {
                                    "id": 12345,
                                    "table_name": "users",
                                    "record_id": 456,
                                    "operation": "UPDATE",
                                    "old_values": {"is_active": True},
                                    "new_values": {"is_active": False},
                                    "changed_by": 1,
                                    "changed_at": "2024-01-15T14:30:00Z"
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name="Пустой журнал аудита",
                        summary="Когда записей аудита нет",
                        value={
                            "count": 0,
                            "next": None,
                            "previous": None,
                            "results": []
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Журнал аудита']
    )
    def get(self, request):
        logs = AuditLog.objects.all()
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(logs, request)

        if page is not None:
            serializer = AuditLogSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = AuditLogSerializer(logs, many=True)
        return Response(serializer.data)


class BatchLogDeleteView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken, IsAdmin]

    @extend_schema(
        summary="Удалить запись журнала батчевого импорта",
        description="""
            Удаление записи журнала батчевого импорта

            Полностью удаляет запись лога батчевой операции по её ID.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут удалять записи логов батчевых операций
            """,
        parameters=[
            OpenApiParameter(
                name='log_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID записи лога батчевой операции для удаления',
                required=True
            )
        ],
        responses={
            204: OpenApiResponse(
                description='No Content'
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Журнал аудита']
    )
    def delete(self, request, log_id=None):
        try:
            log = BatchLog.objects.get(id=log_id)
        except AuditLog.DoesNotExist:
            return Response(
                {'error': 'Запись не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

        log.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BatchLogListView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken, IsAdmin]
    pagination_class = AuditLogLimitOffsetPagination

    @extend_schema(
        summary="Получить записи журнала батчевого импорта",
        description="""
            Получение записей журнала батчевого импорта

            Возвращает список всех записей логов батчевых операций с пагинацией.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут просматривать логи батчевых операций

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка

            Возвращаемые поля:
            - id: Идентификатор записи
            - table_name: Имя таблицы, в которую производился импорт
            - total_processed: Общее количество обработанных записей
            - successful: Количество успешно созданных записей
            - failed: Количество записей с ошибками
            - errors: Список ошибок валидации и создания
            - created_ids: ID созданных записей
            - batches_processed: Количество обработанных пачек
            - batch_size: Размер пачки для обработки
            - changed_by: Пользователь, выполнивший операцию
            - created_at: Дата и время создания лога
            """,
        parameters=[
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
                response=BatchLogSerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name="Список логов батчевых операций",
                        summary="Стандартный ответ со списком логов",
                        value={
                            "count": 25,
                            "next": None,
                            "previous": None,
                            "results": [
                                {
                                    "id": 100,
                                    "table_name": "categories",
                                    "total_processed": 50,
                                    "successful": 48,
                                    "failed": 2,
                                    "errors": [
                                        {
                                            "data": {"name": ""},
                                            "name": "unknown",
                                            "error": "Название категории не может быть пустым",
                                            "type": "validation_error"
                                        }
                                    ],
                                    "created_ids": [101, 102, 103],
                                    "batches_processed": 1,
                                    "batch_size": 100,
                                    "changed_by": 1,
                                    "created_at": "2024-01-15T10:30:00Z"
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name="Пустой журнал батчевых операций",
                        summary="Когда логов батчевых операций нет",
                        value={
                            "count": 0,
                            "next": None,
                            "previous": None,
                            "results": []
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Журнал аудита']
    )
    def get(self, request):
        logs = BatchLog.objects.all()
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(logs, request)

        if page is not None:
            serializer = BatchLogSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = BatchLogSerializer(logs, many=True)
        return Response(serializer.data)
