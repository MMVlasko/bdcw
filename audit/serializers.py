from rest_framework import serializers

from audit.models import AuditLog, BatchLog


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ['id', 'table_name', 'record_id', 'operation', 'old_values', 'new_values', 'changed_by', 'changed_at']


class BatchLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = BatchLog
        fields = ['id', 'table_name', 'total_processed', 'successful', 'failed', 'errors', 'created_ids',
                  'batches_processed', 'batch_size', 'changed_by', 'created_at']
