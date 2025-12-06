from rest_framework import serializers

from audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ['id', 'table_name', 'record_id', 'operation', 'old_values', 'new_values', 'changed_by', 'changed_at']
