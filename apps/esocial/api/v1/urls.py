"""
eSocial API v1 - RESTful API para gestão de eventos eSocial

Oferece endpoints para:
- CRUD de eventos
- Envio assíncrono
- Consulta de status e recibos
- Webhooks de notificação
"""

from rest_framework import routers
from .views import (
    EventViewSet,
    BatchViewSet,
    ReceiptViewSet,
    WebhookViewSet,
    DashboardViewSet
)

router = routers.DefaultRouter()
router.register(r'events', EventViewSet, basename='event')
router.register(r'batches', BatchViewSet, basename='batch')
router.register(r'receipts', ReceiptViewSet, basename='receipt')
router.register(r'webhooks', WebhookViewSet, basename='webhook')
router.register(r'dashboard', DashboardViewSet, basename='dashboard')

urlpatterns = router.urls
