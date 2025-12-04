from django.urls import path
from .views import (
    SubscriptionCreateView,
    SubscriptionDeleteView,
    UserSubscriptionsListView,
    UserSubscribersListView,
    CheckSubscriptionView
)

urlpatterns = [
    # Основные операции с подписками
    path('', SubscriptionCreateView.as_view(), name='subscription-create'),
    path('delete/', SubscriptionDeleteView.as_view(), name='subscription-delete'),
    #
    # # Подписки и подписчики пользователя
    path('subscribed/<int:user_id>/', UserSubscriptionsListView.as_view(), name='user-subscriptions'),
    path('subscribers/<int:user_id>/', UserSubscribersListView.as_view(), name='user-subscribers'),

    # Проверка подписки
    path('is_subscribed/', CheckSubscriptionView.as_view(), name='check-subscription')
]