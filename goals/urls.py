from django.urls import path
from .views import GoalViewSet, GoalProgressViewSet

urlpatterns = [
    # Основные пути целей
    path('', GoalViewSet.as_view({'get': 'list', 'post': 'create'}), name='goal-list'),
    path('<int:pk>/', GoalViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='goal-detail'),

    # Кастомные эндпоинты целей
    path('user/<int:user_id>/', GoalViewSet.as_view({'get': 'user_goals'}), name='user-goals'),
    path('category/<int:category_id>/', GoalViewSet.as_view({'get': 'category_goals'}), name='category-goals'),

    # Основные пути прогресса
    path('progress/', GoalProgressViewSet.as_view({'get': 'list', 'post': 'create'}), name='progress-list'),
    path('progress/<int:pk>/', GoalProgressViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='progress-detail'),

    # Кастомные эндпоинты прогресса
    path('progress/goal/<int:goal_id>/', GoalProgressViewSet.as_view({'get': 'goal_progresses'}),
         name='progress-by-goal'),
]