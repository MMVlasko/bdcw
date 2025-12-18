from django.urls import path
from .views import (
    AuditLogListView,
    AuditLogDeleteView,
    BatchLogListView,
    BatchLogDeleteView
)

urlpatterns = [
    path('', AuditLogListView.as_view(), name='audit-logs'),
    path('delete/<int:log_id>/', AuditLogDeleteView.as_view(), name='audit-log-delete'),
    path('batch/', BatchLogListView.as_view(), name='batch-logs'),
    path('batch/delete/<int:log_id>/', BatchLogDeleteView.as_view(), name='batch-log-delete'),
]
