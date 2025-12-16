from django.urls import path
from .views import (
    GetUsersByCompletedGoalsView, GetUsersByHabitsConsistencyView, GetUsersBySubscribersCountView,
    GetCategoriesByPopularityView, GetChallengesByPopularityView
)

urlpatterns = [
    path('users_by_completed_goals', GetUsersByCompletedGoalsView.as_view(), name='users-by-completed-goals'),
    path('users_by_habits_consistency', GetUsersByHabitsConsistencyView.as_view(), name='users-by-habits-consistency'),
    path('users_by_subscribers_count', GetUsersBySubscribersCountView.as_view(), name='users-by-subscribers-count'),
    path('categories_by_popularity', GetCategoriesByPopularityView.as_view(), name='categories-by-popularity'),
    path('challenges_by_popularity', GetChallengesByPopularityView.as_view(), name='challenges-by-popularity')
]