"""
eSocial API v1 - Serializers para validação e serialização de dados
"""

from rest_framework import serializers
from apps.esocial.models import Event, Batch, Receipt, WebhookSubscription


class EventSerializer(serializers.ModelSerializer):
    """Serializer para eventos eSocial"""
    
    class Meta:
        model = Event
        fields = [
            'id', 'event_id', 'event_type', 'version', 'xml_content',
            'status', 'error_message', 'retry_count', 'created_at',
            'updated_at', 'sent_at', 'receipt'
        ]
        read_only_fields = ['id', 'event_id', 'created_at', 'updated_at', 'sent_at']
    
    def create(self, validated_data):
        # Gera event_id único se não fornecido
        if 'event_id' not in validated_data:
            from django.utils.crypto import get_random_string
            validated_data['event_id'] = f"ID{get_random_string(20)}"
        return super().create(validated_data)


class EventSendSerializer(serializers.Serializer):
    """Serializer para envio de eventos"""
    
    cert_path = serializers.CharField(required=True, help_text="Caminho do certificado digital")
    cert_password = serializers.CharField(required=True, write_only=True, help_text="Senha do certificado")
    environment = serializers.ChoiceField(
        choices=[
            ('producao', 'Produção'),
            ('producao_restrita', 'Produção Restrita'),
            ('homologacao', 'Homologação'),
            ('desenvolvimento', 'Desenvolvimento')
        ],
        default='producao_restrita'
    )


class BatchSerializer(serializers.ModelSerializer):
    """Serializer para lotes de eventos"""
    
    events_count = serializers.SerializerMethodField()
    events_list = serializers.SerializerMethodField()
    
    class Meta:
        model = Batch
        fields = [
            'id', 'batch_id', 'events_count', 'events_list',
            'status', 'created_at', 'updated_at', 'sent_at'
        ]
        read_only_fields = ['id', 'batch_id', 'created_at', 'updated_at', 'sent_at']
    
    def get_events_count(self, obj):
        return obj.events.count()
    
    def get_events_list(self, obj):
        return [
            {
                'event_id': e.event_id,
                'event_type': e.event_type,
                'status': e.status
            }
            for e in obj.events.all()[:10]  # Limita a 10 para não sobrecarregar
        ]


class ReceiptSerializer(serializers.ModelSerializer):
    """Serializer para recibos do eSocial"""
    
    event_id = serializers.CharField(source='event.event_id', read_only=True)
    event_type = serializers.CharField(source='event.event_type', read_only=True)
    
    class Meta:
        model = Receipt
        fields = [
            'id', 'event_id', 'event_type', 'receipt_number',
            'received_at', 'protocol', 'xml_response', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class WebhookSerializer(serializers.ModelSerializer):
    """Serializer para webhooks"""
    
    is_active = serializers.BooleanField(default=True)
    
    class Meta:
        model = WebhookSubscription
        fields = [
            'id', 'url', 'events', 'is_active', 'secret_token',
            'last_triggered_at', 'success_count', 'failure_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'secret_token', 'created_at', 'updated_at']
        extra_kwargs = {
            'secret_token': {'write_only': True}
        }
    
    def create(self, validated_data):
        # Gera token secreto se não fornecido
        if 'secret_token' not in validated_data:
            from django.utils.crypto import get_random_string
            validated_data['secret_token'] = get_random_string(32)
        return super().create(validated_data)


class DashboardSerializer(serializers.Serializer):
    """Serializer para dados do dashboard"""
    
    total_events = serializers.IntegerField()
    events_last_7_days = serializers.IntegerField()
    success_rate_30_days = serializers.FloatField()
    status_breakdown = serializers.DictField()
    top_event_types = serializers.ListField()
    recent_errors = serializers.ListField()
    period = serializers.DictField()


class WebhookTestSerializer(serializers.Serializer):
    """Serializer para teste de webhook"""
    
    url = serializers.URLField(required=True)
    timeout = serializers.IntegerField(default=10, min_value=1, max_value=60)
