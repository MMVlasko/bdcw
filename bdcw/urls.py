# bdcw/urls.py
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from rest_framework import permissions, serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample




# ================== ОБЫЧНЫЕ VIEWS ==================
def home(request):
    return HttpResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>BDCW API</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 40px;
                    background: #f5f5f5;
                }
                .container {
                    max-width: 800px;
                    margin: 0 auto;
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                h1 { color: #2c3e50; }
                .success { color: #27ae60; font-size: 24px; }
                .link-box {
                    background: #3498db;
                    color: white;
                    padding: 15px;
                    margin: 10px 0;
                    border-radius: 5px;
                    text-decoration: none;
                    display: block;
                    transition: background 0.3s;
                }
                .link-box:hover {
                    background: #2980b9;
                    transform: translateY(-2px);
                    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                }
                .api-box {
                    background: #2ecc71;
                    margin-top: 10px;
                }
                .api-box:hover {
                    background: #27ae60;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 BDCW API Server</h1>
                <p class="success">✅ Сервер успешно запущен!</p>

                <p>Доступные endpoints:</p>

                <a class="link-box" href="/api/schema/swagger/">
                    📚 Swagger UI - интерактивная документация
                </a>

                <a class="link-box" href="/api/schema/redoc/">
                    📖 ReDoc - альтернативная документация
                </a>

                <a class="link-box" href="/admin/">
                    ⚙️ Админ панель Django
                </a>

                <a class="link-box" href="/api/schema/">
                    🔧 Raw OpenAPI Schema (YAML)
                </a>

                <h3 style="margin-top: 30px;">API Endpoints:</h3>

                <a class="link-box api-box" href="/api/test/">
                    🧪 /api/test/ - Тестовый endpoint
                </a>

                <a class="link-box api-box" href="/api/schema/swagger/#/Тестирование/api_greet_create">
                    👋 /api/greet/ - Приветствие (POST)
                </a>

                <a class="link-box api-box" href="/api/search/?name=Иван&min_age=20">
                    🔍 /api/search/ - Поиск с параметрами
                </a>

                <div style="margin-top: 30px; color: #7f8c8d;">
                    <p><strong>Техническая информация:</strong></p>
                    <p>• Django 5.2.8 + DRF + drf-spectacular</p>
                    <p>• PostgreSQL в Docker</p>
                    <p>• Порт: 8080 (host) → 8000 (container)</p>
                    <p>• OpenAPI 3.0 спецификация</p>
                </div>
            </div>
        </body>
        </html>
    """)


# ================== URL PATTERNS ==================
urlpatterns = [
    # Основные пути
    path('', home, name='home'),
    path('admin/', admin.site.urls),


    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Swagger UI
    path('api/schema/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    # ReDoc
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    path('api/users/', include('core.urls')),
    path('api/categories/', include('categories.urls')),
    path('api/goals/', include('goals.urls')),
    path('api/habits/', include('habits.urls')),
    path('api/subscriptions/', include('subscriptions.urls'))
]