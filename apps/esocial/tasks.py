"""
eSocial - Tarefas Assíncronas com Celery

Módulo responsável pelo processamento em segundo plano de:
- Envio de eventos para o eSocial
- Validação de XML
- Assinatura digital
- Notificação de webhooks
- Retry de falhas
"""

import logging
from datetime import datetime
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.esocial.models import Event, Receipt, WebhookSubscription
from apps.esocial.utils import (
    validate_xml,
    sign_xml,
    send_to_esocial,
    translate_error
)

logger = logging.getLogger('esocial.celery')


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def send_event_to_esocial_task(self, event_id, xml_content, environment='producao_restrita'):
    """
    Tarefa assíncrona para enviar evento ao eSocial
    
    Fluxo:
    1. Valida XML contra XSD oficial
    2. Assina digitalmente
    3. Envia para webservice do eSocial
    4. Salva recibo
    5. Notifica webhooks
    
    Args:
        event_id: ID do evento no banco
        xml_content: Conteúdo XML do evento (pode ou não estar assinado)
        environment: Ambiente do eSocial (producao, producao_restrita, etc)
    """
    try:
        with transaction.atomic():
            event = Event.objects.select_for_update().get(pk=event_id)
            
            # Atualiza status
            event.status = 'SENDING'
            event.retry_count += 1
            event.save(update_fields=['status', 'retry_count', 'updated_at'])
            
            logger.info(f"Iniciando envio do evento {event.event_id} ({event.event_type})")
            
            # Passo 1: Validar XML (se ainda não estiver assinado)
            if not '<ds:Signature' in xml_content:
                logger.debug(f"Validando XML do evento {event.event_id}")
                validation_result = validate_xml(xml_content, event.event_type)
                
                if not validation_result['valid']:
                    errors = validation_result.get('errors', [])
                    error_msg = "; ".join([str(e) for e in errors])
                    raise Exception(f"Validação XML falhou: {error_msg}")
                
                logger.debug(f"XML válido para evento {event.event_id}")
            
            # Passo 2: Assinar XML (se ainda não estiver assinado)
            if not '<ds:Signature' in xml_content:
                logger.debug(f"Assinando evento {event.event_id}")
                # Nota: Em produção, o certificado deve vir de configuração segura
                from django.conf import settings
                cert_path = getattr(settings, 'ESOCIAL_CERT_PATH', None)
                cert_password = getattr(settings, 'ESOCIAL_CERT_PASSWORD', None)
                
                if not cert_path or not cert_password:
                    raise Exception("Certificado digital não configurado")
                
                xml_content = sign_xml(xml_content, cert_path, cert_password)
                logger.debug(f"Evento {event.event_id} assinado com sucesso")
            
            # Passo 3: Enviar para eSocial
            logger.debug(f"Enviando evento {event.event_id} para eSocial ({environment})")
            result = send_to_esocial(
                xml_content=xml_content,
                cert_path=getattr(settings, 'ESOCIAL_CERT_PATH'),
                cert_password=getattr(settings, 'ESOCIAL_CERT_PASSWORD'),
                environment=environment
            )
            
            if not result['success']:
                # Traduz erro para mensagem amigável
                error_info = translate_error(result.get('error', ''))
                raise Exception(error_info['friendly_message'])
            
            # Passo 4: Salvar recibo
            receipt_data = result.get('receipt', {})
            receipt = Receipt.objects.create(
                event=event,
                receipt_number=receipt_data.get('nrRecibo', ''),
                received_at=datetime.now(),
                protocol=receipt_data.get('protocolo', ''),
                xml_response=result.get('raw_response', '')
            )
            
            # Atualiza evento
            event.status = 'SENT'
            event.sent_at = timezone.now()
            event.error_message = None
            event.save(update_fields=['status', 'sent_at', 'error_message', 'updated_at'])
            
            logger.info(f"Evento {event.event_id} enviado com sucesso. Recibo: {receipt.receipt_number}")
            
            # Passo 5: Notificar webhooks (em outra task para não bloquear)
            notify_webhooks_task.delay(event.id, 'SENT', receipt.receipt_number)
            
            return {
                'success': True,
                'event_id': event.event_id,
                'receipt': receipt.receipt_number
            }
            
    except Exception as exc:
        logger.error(f"Erro ao enviar evento {event_id}: {str(exc)}", exc_info=True)
        
        # Atualiza status do evento
        with transaction.atomic():
            event = Event.objects.get(pk=event_id)
            event.status = 'ERROR'
            event.error_message = str(exc)
            event.save(update_fields=['status', 'error_message', 'updated_at'])
            
            # Notifica webhook de erro
            notify_webhooks_task.delay(event.id, 'ERROR', str(exc))
        
        # Retry com backoff exponencial
        if self.request.retries < self.max_retries:
            logger.warning(f"Tentativa {self.request.retries + 1} falhou. Retry em {self.default_retry_delay}s")
            raise self.retry(exc=exc, countdown=self.default_retry_delay * (2 ** self.request.retries))
        else:
            logger.error(f"Evento {event_id} falhou após {self.max_retries} tentativas")
            return {
                'success': False,
                'event_id': event_id,
                'error': str(exc)
            }


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def notify_webhooks_task(self, event_id, new_status, extra_data=None):
    """
    Notifica webhooks cadastrados sobre mudanças de status de eventos
    
    Args:
        event_id: ID do evento
        new_status: Novo status do evento
        extra_data: Dados adicionais (ex: número do recibo, mensagem de erro)
    """
    import requests
    from django.conf import settings
    
    try:
        event = Event.objects.get(pk=event_id)
        webhooks = WebhookSubscription.objects.filter(is_active=True)
        
        if not webhooks.exists():
            logger.debug("Nenhum webhook ativo cadastrado")
            return
        
        payload = {
            'event': f'esocial.event.{new_status.lower()}',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'event_id': event.event_id,
                'event_type': event.event_type,
                'status': new_status,
                'extra_data': extra_data
            }
        }
        
        notified_count = 0
        failed_count = 0
        
        for webhook in webhooks:
            # Verifica se este tipo de evento deve ser notificado
            if webhook.events and event.event_type not in webhook.events:
                continue
            
            try:
                headers = {
                    'Content-Type': 'application/json',
                    'X-Webhook-Signature': generate_webhook_signature(payload, webhook.secret_token)
                }
                
                response = requests.post(
                    webhook.url,
                    json=payload,
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code in [200, 201, 202, 204]:
                    notified_count += 1
                    webhook.success_count += 1
                    webhook.last_triggered_at = timezone.now()
                    logger.debug(f"Wehook {webhook.url} notificado com sucesso")
                else:
                    failed_count += 1
                    webhook.failure_count += 1
                    logger.warning(f"Wehook {webhook.url} retornou status {response.status_code}")
                
                webhook.save(update_fields=[
                    'success_count' if notified_count > 0 else 'failure_count',
                    'last_triggered_at' if notified_count > 0 else None,
                    'updated_at'
                ])
                
            except requests.exceptions.Timeout:
                failed_count += 1
                webhook.failure_count += 1
                webhook.save(update_fields=['failure_count', 'updated_at'])
                logger.warning(f"Timeout ao notificar webhook {webhook.url}")
            except Exception as e:
                failed_count += 1
                webhook.failure_count += 1
                webhook.save(update_fields=['failure_count', 'updated_at'])
                logger.error(f"Erro ao notificar webhook {webhook.url}: {str(e)}")
        
        logger.info(f"Notificação webhooks concluída: {notified_count} sucesso, {failed_count} falhas")
        
    except Exception as exc:
        logger.error(f"Erro na task de notificação de webhooks: {str(exc)}", exc_info=True)
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=self.default_retry_delay)


def generate_webhook_signature(payload, secret_token):
    """
    Gera assinatura HMAC para segurança do webhook
    
    Args:
        payload: Dados do payload
        secret_token: Token secreto do webhook
    
    Returns:
        Hash SHA256 em hex
    """
    import hmac
    import hashlib
    import json
    
    if not secret_token:
        return ''
    
    payload_str = json.dumps(payload, sort_keys=True)
    signature = hmac.new(
        secret_token.encode('utf-8'),
        payload_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return f"sha256={signature}"


@shared_task
def cleanup_old_events_task(days_to_keep=90):
    """
    Limpa eventos antigos para manter o banco de dados otimizado
    
    Args:
        days_to_keep: Número de dias para manter eventos (default: 90)
    """
    from django.utils import timezone
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    
    # Eventos enviados e com recibo podem ser arquivados
    old_events = Event.objects.filter(
        status='SENT',
        created_at__lt=cutoff_date
    )
    
    count = old_events.count()
    
    # Em vez de deletar, podemos arquivar ou apenas logar
    logger.info(f"{count} eventos mais antigos que {cutoff_date.date()} identificados para limpeza")
    
    # Descomente para deletar efetivamente:
    # old_events.delete()
    
    return {'cleaned_count': count, 'cutoff_date': cutoff_date.isoformat()}


@shared_task
def retry_failed_events_task(max_retries=3):
    """
    Tenta reenviar eventos que falharam temporariamente
    
    Args:
        max_retries: Número máximo de tentativas
    """
    from django.utils import timezone
    from datetime import timedelta
    
    # Eventos com erro nas últimas 24 horas que podem ser retry
    retryable_events = Event.objects.filter(
        status='ERROR',
        retry_count__lt=max_retries,
        updated_at__gte=timezone.now() - timedelta(hours=24)
    )
    
    logger.info(f"Identificados {retryable_events.count()} eventos para retry")
    
    for event in retryable_events:
        # Reenvia para fila
        send_event_to_esocial_task.delay(
            event.id,
            event.xml_content,
            event.version
        )
        logger.info(f"Evento {event.event_id} reenviado para fila de retry")
    
    return {'retry_count': retryable_events.count()}
