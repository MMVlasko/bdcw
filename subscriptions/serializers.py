from rest_framework import serializers
from .models import Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ['subscriber', 'subscribing', 'subscribed_at']


class SubscriptionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ['subscriber', 'subscribing']


class BatchSubscriptionCreateSerializer(serializers.Serializer):
    subscriptions = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False,
        max_length=10000
    )

    batch_size = serializers.IntegerField(
        required=False,
        default=100,
        min_value=1,
        max_value=5000
    )
