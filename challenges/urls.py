from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ChallengeViewSet,
    AppendCategoryToChallengeView,
    DeleteCategoryFromChallengeView,
    AppendGoalToChallengeView,
    DeleteGoalFromChallengeView
)

router = DefaultRouter()
router.register(r'', ChallengeViewSet, basename='challenge')

urlpatterns = [
    path('', include(router.urls)),

    path('categories/append/',
         AppendCategoryToChallengeView.as_view(),
         name='append-category-to-challenge'),

    path('categories/delete/',
         DeleteCategoryFromChallengeView.as_view(),
         name='delete-category-from-challenge'),

    path('goals/append/',
         AppendGoalToChallengeView.as_view(),
         name='append-goal-to-challenge'),

    path('goals/delete/',
         DeleteGoalFromChallengeView.as_view(),
         name='delete-goal-from-challenge'),
]