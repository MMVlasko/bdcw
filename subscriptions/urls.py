from django.urls import path
from .views import (
    SubscriptionCreateView,
    SubscriptionDeleteView,
    UserSubscriptionsListView,
    UserSubscribersListView,
    CheckSubscriptionView,
    BatchSubscriptionCreateView
)

urlpatterns = [
    path('', SubscriptionCreateView.as_view(), name='subscription-create'),
    path('delete/', SubscriptionDeleteView.as_view(), name='subscription-delete'),

    path('subscribed/<int:user_id>/', UserSubscriptionsListView.as_view(), name='user-subscriptions'),
    path('subscribers/<int:user_id>/', UserSubscribersListView.as_view(), name='user-subscribers'),

    path('is_subscribed/', CheckSubscriptionView.as_view(), name='check-subscription'),
    path('batch-import/', BatchSubscriptionCreateView.as_view(), name='batch-subscription-create')
]
