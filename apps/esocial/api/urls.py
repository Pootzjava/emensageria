"""
eSocial API v1 - URLs principais

Inclui:
- Rotas da API v1
- Documentação Swagger/OpenAPI
- Schema OpenAPI para download
"""

from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView
)

urlpatterns = [
    # API v1 endpoints
    path('v1/', include('apps.esocial.api.v1.urls')),
    
    # Documentação OpenAPI/Swagger
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]