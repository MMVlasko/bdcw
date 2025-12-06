from django.urls import path
from .views import (
    AuditLogListView,
    AuditLogDeleteView
)

urlpatterns = [
    path('', AuditLogListView.as_view(), name='audit-logs'),
    path('delete/<int:log_id>/', AuditLogDeleteView.as_view(), name='audit-log-delete'),
]