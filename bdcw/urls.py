from django.contrib import admin
from django.urls import path, include

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path('', SpectacularSwaggerView.as_view(), name='home'),
    path('admin/', admin.site.urls),


    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),

    path('api/schema/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    path('api/users/', include('core.urls')),
    path('api/categories/', include('categories.urls')),
    path('api/goals/', include('goals.urls')),
    path('api/habits/', include('habits.urls')),
    path('api/subscriptions/', include('subscriptions.urls')),
    path('api/challenges/', include('challenges.urls')),
    path('api/audit/', include('audit.urls')),
    path('api/analytics/', include('analytics.urls'))
]