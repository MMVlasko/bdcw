from django.urls import path
from .views import HabitViewSet, HabitLogViewSet

urlpatterns = [
    # Основные пути целей
    path('', HabitViewSet.as_view({'get': 'list', 'post': 'create'}), name='habit-list'),
    path('<int:pk>/', HabitViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='habit-detail'),

    # Кастомные эндпоинты целей
    path('user/<int:user_id>/', HabitViewSet.as_view({'get': 'user_habits'}), name='user-habits'),
    path('category/<int:category_id>/', HabitViewSet.as_view({'get': 'category_habits'}), name='category-habits'),

    # Основные пути прогресса
    path('log/', HabitLogViewSet.as_view({'get': 'list', 'post': 'create'}), name='log-list'),
    path('log/<int:pk>/', HabitLogViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='log-detail'),

    # Кастомные эндпоинты прогресса
    path('log/habit/<int:habit_id>/', HabitLogViewSet.as_view({'get': 'habit_logs'}),
         name='log-by-habit'),
]