from django.db import models
from core.models import User


class Subscription(models.Model):
    class Meta:
        db_table = 'subscriptions'

    pk = models.CompositePrimaryKey('subscriber', 'subscribing')

    subscriber = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='subscriptions_made'
    )

    subscribing = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='subscriptions_received'
    )

    subscribed_at = models.DateTimeField('Подписан', auto_now_add=True)

