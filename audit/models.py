from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

from core.models import User


class NowDefaultField(models.DateTimeField):
    def __init__(self, *args, **kwargs):
        kwargs['default'] = timezone.now
        kwargs['editable'] = False
        super().__init__(*args, **kwargs)

    def db_type(self, connection):
        if connection.vendor == 'postgresql':
            return 'TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP'
        return super().db_type(connection)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs.pop('default', None)
        kwargs.pop('editable', None)
        return name, path, args, kwargs


class AuditLog(models.Model):
    class Operation(models.TextChoices):
        INSERT = 'INSERT', 'Insert'
        UPDATE = 'UPDATE', 'Update'
        DELETE = 'DELETE', 'Delete'

    id = models.BigAutoField(primary_key=True)

    table_name = models.CharField(max_length=100)
    record_id = models.BigIntegerField(null=True)
    operation = models.CharField(max_length=10, choices=Operation.choices)
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    changed_at = NowDefaultField()

    class Meta:
        db_table = 'audit_logs'


class BatchLog(models.Model):
    class Meta:
        db_table = 'batch_logs'

    id = models.BigAutoField(
        primary_key=True
    )

    table_name = models.CharField(
        max_length=100
    )

    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='batch_logs'
    )

    total_processed = models.PositiveIntegerField(
        default=0
    )

    successful = models.PositiveIntegerField(
        default=0
    )

    failed = models.PositiveIntegerField(
        default=0
    )

    errors = models.JSONField(
        default=list,
        encoder=DjangoJSONEncoder
    )

    created_ids = ArrayField(
        models.BigIntegerField(),
        default=list,
        blank=True
    )

    batches_processed = models.PositiveIntegerField(
        default=0
    )

    batch_size = models.PositiveIntegerField(
        default=100
    )

    created_at = NowDefaultField()
