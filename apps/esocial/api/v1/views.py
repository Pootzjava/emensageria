"""
eSocial API v1 - ViewSets para operações REST

Endpoints disponíveis:
- /api/v1/events/ - CRUD de eventos
- /api/v1/batches/ - Gerenciamento de lotes
- /api/v1/receipts/ - Consulta de recibos
- /api/v1/webhooks/ - Configuração de webhooks
- /api/v1/dashboard/ - Métricas e estatísticas
"""

import json
from datetime import datetime, timedelta
from django.db.models import Count, Q, F
from django.utils import timezone
from rest_framework import viewsets, status, decorators, permissions
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from apps.esocial.models import Event, Batch, Receipt, WebhookSubscription
from apps.esocial.tasks import send_event_to_esocial_task
from apps.esocial.utils import (
    validate_xml,
    sign_xml,
    send_to_esocial,
    translate_error
)
from .serializers import (
    EventSerializer,
    BatchSerializer,
    ReceiptSerializer,
    WebhookSerializer,
    DashboardSerializer,
    EventSendSerializer,
    WebhookTestSerializer
)


class EventViewSet(viewsets.ModelViewSet):
    """
    CRUD completo de eventos eSocial
    
    Permite criar, listar, recuperar, atualizar e deletar eventos.
    Suporta envio assíncrono para o eSocial.
    """
    queryset = Event.objects.all().order_by('-created_at')
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Criar e enviar evento",
        description="Cria um novo evento e opcionalmente envia para o eSocial"
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        event = serializer.save()
        
        # Se solicitado, envia para o eSocial
        if request.data.get('send_now', False):
            try:
                # Valida XML
                validation_result = validate_xml(event.xml_content, event.event_type)
                if not validation_result['valid']:
                    raise ValidationError(validation_result['errors'])
                
                # Assina XML
                signed_xml = sign_xml(
                    event.xml_content,
                    cert_path=request.data.get('cert_path'),
                    cert_password=request.data.get('cert_password')
                )
                
                # Envia assincronamente
                task = send_event_to_esocial_task.delay(
                    event.id,
                    signed_xml,
                    request.data.get('environment', 'producao_restrita')
                )
                
                return Response({
                    'event': serializer.data,
                    'task_id': task.id,
                    'status': 'queued'
                }, status=status.HTTP_202_ACCEPTED)
                
            except Exception as e:
                event.status = 'ERROR'
                event.error_message = str(e)
                event.save(update_fields=['status', 'error_message'])
                raise ValidationError(str(e))
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        summary="Validar evento",
        description="Valida o XML do evento contra o XSD oficial sem enviar"
    )
    @decorators.action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        event = self.get_object()
        
        try:
            result = validate_xml(event.xml_content, event.event_type)
            return Response({
                'valid': result['valid'],
                'errors': result.get('errors', []),
                'warnings': result.get('warnings', [])
            })
        except Exception as e:
            return Response({
                'valid': False,
                'errors': [str(e)]
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Enviar evento",
        description="Envia evento já criado para o eSocial"
    )
    @decorators.action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        event = self.get_object()
        
        if event.status == 'SENT':
            raise ValidationError("Evento já foi enviado")
        
        try:
            cert_path = request.data.get('cert_path')
            cert_password = request.data.get('cert_password')
            environment = request.data.get('environment', 'producao_restrita')
            
            # Assina XML
            signed_xml = sign_xml(event.xml_content, cert_path, cert_password)
            
            # Envia assincronamente
            task = send_event_to_esocial_task.delay(
                event.id,
                signed_xml,
                environment
            )
            
            return Response({
                'task_id': task.id,
                'status': 'queued',
                'message': 'Evento enviado para fila de processamento'
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            error_info = translate_error(str(e))
            return Response({
                'error': error_info['friendly_message'],
                'details': error_info['technical_details']
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Listar por período",
        parameters=[
            OpenApiParameter('start_date', OpenApiTypes.DATE, description='Data inicial'),
            OpenApiParameter('end_date', OpenApiTypes.DATE, description='Data final'),
            OpenApiParameter('event_type', OpenApiTypes.STR, description='Tipo de evento'),
            OpenApiParameter('status', OpenApiTypes.STR, description='Status do evento')
        ]
    )
    @decorators.action(detail=False, methods=['get'])
    def by_period(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        event_type = request.query_params.get('event_type')
        evt_status = request.query_params.get('status')
        
        queryset = self.filter_queryset(self.get_queryset())
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        if evt_status:
            queryset = queryset.filter(status=evt_status)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class BatchViewSet(viewsets.ModelViewSet):
    """
    Gerenciamento de lotes de eventos
    
    Permite criar lotes, adicionar eventos e enviar lotes completos.
    """
    queryset = Batch.objects.all().order_by('-created_at')
    serializer_class = BatchSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Adicionar evento ao lote",
        description="Adiciona um evento existente a um lote"
    )
    @decorators.action(detail=True, methods=['post'])
    def add_event(self, request, pk=None):
        batch = self.get_object()
        event_id = request.data.get('event_id')
        
        if not event_id:
            raise ValidationError("event_id é obrigatório")
        
        try:
            event = Event.objects.get(pk=event_id)
            batch.events.add(event)
            batch.save()
            
            return Response({
                'message': f'Evento {event.event_id} adicionado ao lote {batch.batch_id}',
                'batch_events_count': batch.events.count()
            })
        except Event.DoesNotExist:
            raise ValidationError("Evento não encontrado")
    
    @extend_schema(
        summary="Enviar lote",
        description="Envia todos os eventos do lote para o eSocial"
    )
    @decorators.action(detail=True, methods=['post'])
    def send_batch(self, request, pk=None):
        batch = self.get_object()
        
        if batch.events.filter(status='SENT').exists():
            raise ValidationError("Lote já contém eventos enviados")
        
        events = batch.events.filter(status='CREATED')
        if not events.exists():
            raise ValidationError("Nenhum evento válido no lote")
        
        # Envia cada evento assincronamente
        task_ids = []
        for event in events:
            task = send_event_to_esocial_task.delay(
                event.id,
                event.xml_content,  # Assume que já está assinado ou será assinado na task
                request.data.get('environment', 'producao_restrita')
            )
            task_ids.append(task.id)
        
        return Response({
            'message': f'{events.count()} eventos enviados para processamento',
            'task_ids': task_ids,
            'batch_id': batch.batch_id
        }, status=status.HTTP_202_ACCEPTED)


class ReceiptViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Consulta de recibos do eSocial
    
    Apenas leitura de recibos de eventos enviados.
    """
    queryset = Receipt.objects.all().order_by('-received_at')
    serializer_class = ReceiptSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Buscar por evento",
        description="Busca recibo de um evento específico"
    )
    @decorators.action(detail=False, methods=['get'])
    def by_event(self, request):
        event_id = request.query_params.get('event_id')
        
        if not event_id:
            raise ValidationError("event_id é obrigatório")
        
        try:
            receipt = Receipt.objects.get(event__event_id=event_id)
            serializer = self.get_serializer(receipt)
            return Response(serializer.data)
        except Receipt.DoesNotExist:
            return Response(
                {'message': 'Recibo não encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )


class WebhookViewSet(viewsets.ModelViewSet):
    """
    Gerenciamento de Webhooks
    
    Configura endpoints para receber notificações automáticas
    sobre mudanças de status de eventos.
    """
    queryset = WebhookSubscription.objects.all().order_by('-created_at')
    serializer_class = WebhookSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Testar webhook",
        description="Envia um evento de teste para o webhook configurado"
    )
    @decorators.action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        webhook = self.get_object()
        
        import requests
        
        test_payload = {
            'event': 'webhook.test',
            'timestamp': datetime.now().isoformat(),
            'data': {
                'message': 'Este é um teste de webhook do eSocial',
                'webhook_id': webhook.id,
                'url': webhook.url
            }
        }
        
        try:
            response = requests.post(
                webhook.url,
                json=test_payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            success = response.status_code in [200, 201, 202, 204]
            
            return Response({
                'success': success,
                'status_code': response.status_code,
                'response_time_ms': response.elapsed.total_seconds() * 1000,
                'message': 'Webhook funcionando!' if success else 'Falha no webhook'
            })
            
        except requests.exceptions.Timeout:
            return Response({
                'success': False,
                'error': 'Timeout ao conectar com webhook'
            }, status=status.HTTP_408_REQUEST_TIMEOUT)
        except requests.exceptions.ConnectionError:
            return Response({
                'success': False,
                'error': 'Não foi possível conectar ao webhook'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class DashboardViewSet(viewsets.ViewSet):
    """
    Dashboard e métricas do eSocial
    
    Fornece estatísticas, gráficos e indicadores de desempenho.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(summary="Visão geral do dashboard")
    @decorators.action(detail=False, methods=['get'])
    def overview(self, request):
        now = timezone.now()
        last_7_days = now - timedelta(days=7)
        last_30_days = now - timedelta(days=30)
        
        # Eventos totais
        total_events = Event.objects.count()
        
        # Eventos por status
        status_counts = Event.objects.values('status').annotate(
            count=Count('id')
        )
        
        # Eventos últimos 7 dias
        events_7d = Event.objects.filter(created_at__gte=last_7_days).count()
        
        # Taxa de sucesso últimos 30 dias
        events_30d = Event.objects.filter(created_at__gte=last_30_days)
        success_count = events_30d.filter(status='SENT').count()
        success_rate = (success_count / events_30d.count() * 100) if events_30d.exists() else 0
        
        # Top tipos de evento
        top_events = Event.objects.values('event_type').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Erros recentes
        recent_errors = Event.objects.filter(
            status='ERROR',
            created_at__gte=last_7_days
        ).order_by('-created_at')[:5]
        
        data = {
            'total_events': total_events,
            'events_last_7_days': events_7d,
            'success_rate_30_days': round(success_rate, 2),
            'status_breakdown': {item['status']: item['count'] for item in status_counts},
            'top_event_types': list(top_events),
            'recent_errors': [
                {
                    'event_id': e.event_id,
                    'event_type': e.event_type,
                    'error': e.error_message,
                    'created_at': e.created_at.isoformat()
                }
                for e in recent_errors
            ],
            'period': {
                'from': last_7_days.isoformat(),
                'to': now.isoformat()
            }
        }
        
        return Response(data)
    
    @extend_schema(
        summary="Estatísticas por período",
        parameters=[
            OpenApiParameter('days', OpenApiTypes.INT, description='Número de dias (default: 30)'),
            OpenApiParameter('group_by', OpenApiTypes.STR, description='Agrupar por: day, week, month')
        ]
    )
    @decorators.action(detail=False, methods=['get'])
    def statistics(self, request):
        days = int(request.query_params.get('days', 30))
        group_by = request.query_params.get('group_by', 'day')
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        events = Event.objects.filter(created_at__gte=start_date)
        
        if group_by == 'day':
            stats = events.extra(
                select={'date': 'DATE(created_at)'}
            ).values('date').annotate(
                total=Count('id'),
                sent=Count('id', filter=Q(status='SENT')),
                error=Count('id', filter=Q(status='ERROR'))
            ).order_by('date')
        elif group_by == 'week':
            stats = events.extra(
                select={'week': "DATE_TRUNC('week', created_at)"}
            ).values('week').annotate(
                total=Count('id'),
                sent=Count('id', filter=Q(status='SENT')),
                error=Count('id', filter=Q(status='ERROR'))
            ).order_by('week')
        else:  # month
            stats = events.extra(
                select={'month': "DATE_TRUNC('month', created_at)"}
            ).values('month').annotate(
                total=Count('id'),
                sent=Count('id', filter=Q(status='SENT')),
                error=Count('id', filter=Q(status='ERROR'))
            ).order_by('month')
        
        return Response({
            'period': {
                'from': start_date.isoformat(),
                'to': end_date.isoformat(),
                'days': days,
                'group_by': group_by
            },
            'statistics': list(stats)
        })
