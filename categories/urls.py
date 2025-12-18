from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, BatchCategoryCreateView

router = DefaultRouter()
router.register(r'', CategoryViewSet, basename='user')

urlpatterns = [
    path('batch-import/', BatchCategoryCreateView.as_view(), name='batch-category-create'),
    path('', include(router.urls))
]
