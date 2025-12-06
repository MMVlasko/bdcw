from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import LimitOffsetPagination

from bdcw.authentication import TokenAuthentication, HasValidToken, IsAdmin
from bdcw.error_responses import (
    UNAUTHORIZED_RESPONSE,
    FORBIDDEN_RESPONSE, NOT_FOUND_RESPONSE, INTERNAL_SERVER_ERROR
)

from .models import AuditLog
from .serializers import AuditLogSerializer


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
        description="Удаление записи журнала аудита",
        parameters=[
            OpenApiParameter(
                name='log_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='ID записи',
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
        description="Получить список записей журнала аудита",
        responses={
            200: AuditLogSerializer(many=True),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
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
