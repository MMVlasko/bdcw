from django.db import connection, transaction, IntegrityError
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample, OpenApiParameter
from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import BatchLog
from bdcw.authentication import TokenAuthentication, HasValidToken, IsAdmin
from bdcw.error_responses import (BAD_REQUEST_RESPONSE, UNAUTHORIZED_RESPONSE, FORBIDDEN_RESPONSE, NOT_FOUND_RESPONSE,
                                  INTERNAL_SERVER_ERROR, BAD_BATCH_REQUEST_RESPONSE)
from core.serializers import BatchOperationLogSerializer
from .models import Category
from .serializers import CategorySerializer, CategoryCreateAndUpdateSerializer, CategoryPartialUpdateSerializer, \
    BatchCategoryCreateSerializer
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
        summary='писок категорий',
        description='''
            Получение списка категорий

            Возвращает список всех категорий с пагинацией.

            Права доступа:
            - Требуется действительный токен

            Пагинация:
            - limit: Количество записей на странице (макс. 100)
            - offset: Смещение от начала списка
            ''',
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
                response=CategorySerializer(many=True),
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Список категорий',
                        summary='Стандартный ответ со списком категорий',
                        value={
                            'count': 25,
                            'next': 'http://127.0.0.1:8080/api/categories/?limit=10&offset=10',
                            'previous': None,
                            'results': [
                                {
                                    'id': 1,
                                    'name': 'Спорт',
                                    'description': 'Спортивные активности и упражнения',
                                    'created_at': '2024-01-01T09:15:30Z',
                                    'updated_at': '2024-01-15T14:20:45Z'
                                }
                            ]
                        }
                    ),
                    OpenApiExample(
                        name='Пустой список категорий',
                        summary='Когда категорий нет',
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
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Категории']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary='Создать категорию',
        description='''
            Создание новой категории

            Создает новую категорию с указанными параметрами.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут создавать категории

            Обязательные поля:
            - name: Название категории (строка, максимум 100 символов, уникальное)

            Опциональные поля:
            - description: Описание категории (текст, может быть null)

            Валидация:
            - Проверка уникальности имени категории
            - Проверка длины названия (максимум 100 символов)
            - Проверка, что название не пустое
            ''',
        request=CategoryCreateAndUpdateSerializer,
        responses={
            201: OpenApiResponse(
                response=CategorySerializer,
                description='Created',
                examples=[
                    OpenApiExample(
                        name='Категория успешно создана',
                        summary='Стандартный ответ при успешном создании',
                        value={
                            'id': 45,
                            'name': 'Программирование',
                            'description': 'Изучение языков программирования и технологий',
                            'created_at': '2024-01-15T10:30:00Z',
                            'updated_at': '2024-01-15T10:30:00Z'
                        }
                    )
                ]
            ),
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
        summary='Получить категорию',
        description='''
            Получение информации о категории

            Возвращает полную информацию о конкретной категории по её ID.

            Права доступа:
            - Требуется действительный токен

            Возвращаемые поля:
            - id: Идентификатор категории
            - name: Название категории
            - description: Описание категории
            - created_at: Дата создания
            - updated_at: Дата обновления
            ''',
        responses={
            200: OpenApiResponse(
                response=CategorySerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Категория с описанием',
                        summary='Информация о категории с описанием',
                        value={
                            'id': 1,
                            'name': 'Спорт',
                            'description': 'Спортивные активности и упражнения',
                            'created_at': '2024-01-01T09:15:30Z',
                            'updated_at': '2024-01-15T14:20:45Z'
                        }
                    ),
                    OpenApiExample(
                        name='Категория без описания',
                        summary='Информация о категории без описания',
                        value={
                            'id': 2,
                            'name': 'Музыка',
                            'description': None,
                            'created_at': '2024-01-02T11:45:20Z',
                            'updated_at': '2024-01-02T11:45:20Z'
                        }
                    )
                ]
            ),
            401: UNAUTHORIZED_RESPONSE,
            403: FORBIDDEN_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            500: INTERNAL_SERVER_ERROR
        },
        tags=['Категории']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary='Обновить категорию',
        description='''
            Полное обновление информации о категории

            Заменяет все данные категории новыми значениями. Все поля обязательны.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут обновлять категории

            Обязательные поля:
            - name: Название категории (строка, максимум 100 символов, уникальное)
            - description: Описание категории (может быть null)

            Валидация:
            - Проверка обязательных полей
            - Проверка уникальности имени категории
            - Проверка длины названия (максимум 100 символов)
            - Проверка, что название не пустое
            ''',
        request=CategoryCreateAndUpdateSerializer,
        responses={
            200: OpenApiResponse(
                response=CategorySerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Категория успешно обновлена',
                        summary='Стандартный ответ при успешном обновлении',
                        value={
                            'id': 1,
                            'name': 'Обновленная категория',
                            'description': 'Обновленное описание категории',
                            'created_at': '2024-01-01T09:15:30Z',
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
        tags=['Категории']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary='Частично обновить категорию',
        description='''
            Частичное обновление информации о категории

            Обновляет только указанные поля категории. Не указанные поля остаются без изменений.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут обновлять категории

            Доступные для обновления поля:
            - name: Название категории
            - description: Описание категории (можно установить в null)

            Особенности:
            - Можно обновлять любое подмножество полей
            - Не требуется передавать все поля
            - Проверка уникальности имени при обновлении
            - Проверка длины названия (максимум 100 символов)
            ''',
        request=CategoryPartialUpdateSerializer,
        responses={
            200: OpenApiResponse(
                response=CategorySerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Обновлено только описание',
                        summary='Обновлено одно поле',
                        value={
                            'id': 1,
                            'name': 'Спорт',
                            'description': 'Новое подробное описание спортивных активностей',
                            'created_at': '2024-01-01T09:15:30Z',
                            'updated_at': '2024-01-15T15:45:00Z'
                        }
                    ),
                    OpenApiExample(
                        name='Обновлено название и описание',
                        summary='Обновлено несколько полей',
                        value={
                            'id': 2,
                            'name': 'Музыкальное искусство',
                            'description': 'Новое описание музыкальной категории',
                            'created_at': '2024-01-02T11:45:20Z',
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
        tags=['Категории']
    )
    def partial_update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary='Удалить категорию',
        description='''
            Удаление категории

            Полностью удаляет категорию из системы.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут удалять категории

            Последствия удаления:
            - Безвозвратное удаление категории
            - Каскадное удаление связей с целями, привычками и челленджами
            ''',
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
        tags=['Категории']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class BatchCategoryCreateView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [HasValidToken, IsAdmin]

    @extend_schema(
        summary='Батчевая загрузка категорий',
        description='''
            Массовое создание категорий

            Создание нескольких категорий за одну операцию с использованием bulk_create.

            Права доступа:
            - Требуется действительный токен
            - Только администраторы могут создавать категории батчами

            Структура запроса:
            - categories: Список объектов категорий (максимум 10,000)
            - batch_size: Размер пачки для обработки (от 1 до 5,000, по умолчанию 100)

            Обязательные поля для каждой категории:
            - name: Название категории (строка, максимум 100 символов, не может быть пустой)

            Опциональные поля:
            - description: Описание категории (текст, может быть null)

            Валидация:
            - Проверка уникальности имен в пределах запроса
            - Проверка уникальности имен относительно существующих категорий
            - Проверка длины названия (максимум 100 символов)
            - Проверка, что название не пустое
            - Проверка типа данных для описания
            ''',
        request=BatchCategoryCreateSerializer,
        responses={
            200: OpenApiResponse(
                response=BatchOperationLogSerializer,
                description='OK',
                examples=[
                    OpenApiExample(
                        name='Полностью успешная операция',
                        summary='Все категории созданы',
                        value={
                            'total_processed': 50,
                            'successful': 50,
                            'failed': 0,
                            'batch_size': 25,
                            'errors': [],
                            'created_ids': [101, 102, 103, 104, 105],
                            'batches_processed': 2
                        }
                    ),
                    OpenApiExample(
                        name='Операция с ошибками',
                        summary='Некоторые категории не созданы',
                        value={
                            'total_processed': 5,
                            'successful': 3,
                            'failed': 2,
                            'batch_size': 100,
                            'errors': [
                                {
                                    'data': {
                                        'name': 'Спорт'
                                    },
                                    'name': 'Спорт',
                                    'error': 'Категория с названием Спорт уже существует',
                                    'type': 'duplicate_error'
                                },
                                {
                                    'data': {
                                        'name': '',
                                        'description': 'Описание'
                                    },
                                    'name': 'unknown',
                                    'error': 'Название категории не может быть пустым',
                                    'type': 'validation_error'
                                }
                            ],
                            'created_ids': [106, 107, 108],
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
        tags=['Категории']
    )
    def post(self, request):
        serializer = BatchCategoryCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Ошибка валидации',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        categories_data = serializer.validated_data['categories']
        batch_size = serializer.validated_data['batch_size']

        operation_log = {
            'total_processed': len(categories_data),
            'successful': 0,
            'failed': 0,
            'errors': [],
            'created_ids': [],
            'batches_processed': 0,
            'batch_size': batch_size
        }

        try:
            validated_categories_data = []
            names_in_request = set()

            for i, category_data in enumerate(categories_data):
                try:
                    name = category_data.get('name', '').strip()

                    if not name:
                        raise ValueError('Название категории не может быть пустым')

                    if name in names_in_request:
                        raise ValueError(f'Название категории {name} дублируется в этом запросе')
                    names_in_request.add(name)

                    description = category_data.get('description')
                    if description is not None and not isinstance(description, str):
                        raise ValueError('Описание должно быть строкой')

                    validated_categories_data.append({
                        'index': i,
                        'data': category_data,
                        'name': name
                    })

                except serializers.ValidationError as e:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': category_data,
                        'name': category_data.get('name', 'unknown'),
                        'error': e.detail,
                        'type': 'validation_error'
                    })
                except Exception as e:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': category_data,
                        'name': category_data.get('name', 'unknown'),
                        'error': str(e),
                        'type': 'validation_error'
                    })

            if not validated_categories_data:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            names = [item['name'] for item in validated_categories_data]
            existing_qs = Category.objects.filter(name__in=names)
            existing_names = set(category.name for category in existing_qs)

            filtered_categories = []

            for item in validated_categories_data:
                name = item['name']

                if name in existing_names:
                    operation_log['failed'] += 1
                    operation_log['errors'].append({
                        'data': item['data'],
                        'name': name,
                        'error': f'Категория с названием {name} уже существует',
                        'type': 'duplicate_error'
                    })
                else:
                    filtered_categories.append(item)

            if not filtered_categories:
                response_serializer = BatchOperationLogSerializer(operation_log)
                return Response(response_serializer.data)

            batches = [
                filtered_categories[i:i + batch_size]
                for i in range(0, len(filtered_categories), batch_size)
            ]

            for batch_index, batch in enumerate(batches):
                categories_to_create = []

                for item in batch:
                    name = item['name']
                    category_data = item['data']

                    try:
                        category = Category(
                            name=name,
                            description=category_data.get('description')
                        )
                        categories_to_create.append(category)

                    except Exception as e:
                        operation_log['failed'] += 1
                        operation_log['errors'].append({
                            'data': category_data,
                            'name': name,
                            'error': str(e),
                            'type': 'creation_error'
                        })

                with connection.cursor() as cursor:
                    cursor.execute('ALTER TABLE categories DISABLE TRIGGER audit_categories_trigger')

                try:
                    with transaction.atomic():
                        if categories_to_create:
                            try:
                                created = Category.objects.bulk_create(
                                    categories_to_create,
                                    batch_size=len(categories_to_create)
                                )
                                operation_log['successful'] += len(created)

                                if created:
                                    created_ids = [category.id for category in created]
                                    operation_log['created_ids'].extend(created_ids)

                            except IntegrityError as e:
                                operation_log['failed'] += len(categories_to_create)
                                operation_log['errors'].append({
                                    'type': 'integrity_error',
                                    'error': 'Нарушение уникальности при bulk_create',
                                    'details': str(e)
                                })
                                raise

                finally:
                    with connection.cursor() as cursor:
                        cursor.execute('ALTER TABLE categories ENABLE TRIGGER audit_categories_trigger')

                operation_log['batches_processed'] += 1

        except Exception as e:
            operation_log['errors'].append({
                'type': 'critical',
                'error': str(e)
            })
            operation_log['failed'] = operation_log['total_processed'] - operation_log['successful']

        batch_log = BatchLog(
            table_name='categories',
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
