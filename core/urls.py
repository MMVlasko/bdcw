from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, LogoutView, LoginView, CleanUnusedTokensView, BatchUserCreateView

router = DefaultRouter()
router.register(r'', UserViewSet, basename='user')

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('clean_unused_tokens/', CleanUnusedTokensView.as_view(), name='clean_unused_tokens'),
    path('batch-import/', BatchUserCreateView.as_view(), name='batch-user-create'),
    path('', include(router.urls))
]