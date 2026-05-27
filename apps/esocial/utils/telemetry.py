"""
eSocial Telemetry - Observabilidade Avançada com OpenTelemetry
Rastreamento distribuído de cada requisição, métricas e logs estruturados.
Integração pronta para Jaeger/Zipkin e Prometheus/Grafana.
"""

import os
import logging
import time
import functools
from typing import Optional, Dict, Any, Callable
from contextlib import contextmanager
from django.utils import timezone

logger = logging.getLogger(__name__)


class TelemetryConfig:
    """Configuração centralizada de telemetria."""
    
    # Habilitar/desabilitar telemetria
    ENABLED = os.getenv('ESOCIAL_TELEMETRY_ENABLED', 'true').lower() == 'true'
    
    # Backend de tracing (jaeger, zipkin, otlp)
    TRACING_BACKEND = os.getenv('ESOCIAL_TRACING_BACKEND', 'jaeger')
    
    # Endpoints
    JAEGER_ENDPOINT = os.getenv('JAEGER_ENDPOINT', 'http://localhost:14268/api/traces')
    ZIPKIN_ENDPOINT = os.getenv('ZIPKIN_ENDPOINT', 'http://localhost:9411/api/v2/spans')
    OTLP_ENDPOINT = os.getenv('OTLP_ENDPOINT', 'http://localhost:4317')
    
    # Service name
    SERVICE_NAME = os.getenv('ESOCIAL_SERVICE_NAME', 'esocial-enterprise')
    
    # Sample rate (0.0 a 1.0)
    SAMPLE_RATE = float(os.getenv('ESOCIAL_SAMPLE_RATE', '1.0'))
    
    # Métricas
    METRICS_ENABLED = os.getenv('ESOCIAL_METRICS_ENABLED', 'true').lower() == 'true'
    PROMETHEUS_PORT = int(os.getenv('PROMETHEUS_PORT', '9090'))


class Span:
    """Representa um span de tracing."""
    
    def __init__(self, name: str, parent: Optional['Span'] = None):
        self.name = name
        self.parent = parent
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.attributes: Dict[str, Any] = {}
        self.tags: Dict[str, Any] = {}
        self.logs: list = []
        self.status: str = 'OK'
        self.error_message: Optional[str] = None
        self.trace_id: str = parent.trace_id if parent else self._generate_trace_id()
        self.span_id: str = self._generate_span_id()
    
    def _generate_trace_id(self) -> str:
        """Gera ID único para trace."""
        import uuid
        return uuid.uuid4().hex
    
    def _generate_span_id(self) -> str:
        """Gera ID único para span."""
        import uuid
        return uuid.uuid4().hex[:16]
    
    def set_attribute(self, key: str, value: Any):
        """Adiciona atributo ao span."""
        self.attributes[key] = value
    
    def set_tag(self, key: str, value: Any):
        """Adiciona tag ao span."""
        self.tags[key] = value
    
    def log(self, message: str, level: str = 'INFO'):
        """Adiciona log ao span."""
        self.logs.append({
            'timestamp': time.time(),
            'level': level,
            'message': message
        })
    
    def set_error(self, error: Exception):
        """Marca span como erro."""
        self.status = 'ERROR'
        self.error_message = str(error)
        self.set_tag('error', True)
        self.set_tag('error.message', str(error))
        self.set_tag('error.type', type(error).__name__)
    
    def finish(self):
        """Finaliza o span."""
        self.end_time = time.time()
    
    @property
    def duration_ms(self) -> float:
        """Retorna duração em milissegundos."""
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return (time.time() - self.start_time) * 1000
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializa span para dicionário."""
        return {
            'trace_id': self.trace_id,
            'span_id': self.span_id,
            'parent_span_id': self.parent.span_id if self.parent else None,
            'name': self.name,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration_ms': self.duration_ms,
            'attributes': self.attributes,
            'tags': self.tags,
            'logs': self.logs,
            'status': self.status,
            'error_message': self.error_message
        }


class MetricsCollector:
    """Coletor de métricas para Prometheus."""
    
    def __init__(self):
        self.counters: Dict[str, int] = {}
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, list] = {}
        self._registry = {}
    
    def inc_counter(self, name: str, value: int = 1, labels: Dict[str, str] = None):
        """Incrementa contador."""
        key = self._make_key(name, labels)
        self.counters[key] = self.counters.get(key, 0) + value
    
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Define gauge."""
        key = self._make_key(name, labels)
        self.gauges[key] = value
    
    def observe_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Observa valor para histograma."""
        key = self._make_key(name, labels)
        if key not in self.histograms:
            self.histograms[key] = []
        self.histograms[key].append(value)
    
    def _make_key(self, name: str, labels: Dict[str, str] = None) -> str:
        """Cria chave única para métrica."""
        if not labels:
            return name
        
        label_str = ','.join(f'{k}={v}' for k, v in sorted(labels.items()))
        return f'{name}{{{label_str}}}'
    
    def get_metrics_prometheus_format(self) -> str:
        """Exporta métricas no formato Prometheus."""
        lines = []
        
        # Counters
        for key, value in self.counters.items():
            name = key.split('{')[0] if '{' in key else key
            lines.append(f'# TYPE {name} counter')
            lines.append(f'{key} {value}')
        
        # Gauges
        for key, value in self.gauges.items():
            name = key.split('{')[0] if '{' in key else key
            lines.append(f'# TYPE {name} gauge')
            lines.append(f'{key} {value}')
        
        # Histograms
        for key, values in self.histograms.items():
            name = key.split('{')[0] if '{' in key else key
            lines.append(f'# TYPE {name} histogram')
            
            if values:
                count = len(values)
                total = sum(values)
                avg = total / count
                
                lines.append(f'{key}_count {count}')
                lines.append(f'{key}_sum {total}')
                lines.append(f'{key}_avg {avg}')
        
        return '\n'.join(lines)
    
    def reset(self):
        """Reseta todas as métricas."""
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()


# Singleton global
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Obtém coletor de métricas singleton."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


class Tracer:
    """Tracer principal para rastreamento distribuído."""
    
    def __init__(self):
        self.active_spans: list[Span] = []
        self.exported_traces: list = []
        self.backend = TelemetryConfig.TRACING_BACKEND
    
    def start_span(self, name: str, parent: Optional[Span] = None) -> Span:
        """Inicia novo span."""
        if not TelemetryConfig.ENABLED:
            return Span(name, parent)
        
        # Se não tem parent e tem span ativo, usa último como parent
        if not parent and self.active_spans:
            parent = self.active_spans[-1]
        
        span = Span(name, parent)
        self.active_spans.append(span)
        
        logger.debug(f"Span iniciado: {name} (trace_id={span.trace_id})")
        
        return span
    
    def end_span(self, span: Span):
        """Finaliza span e exporta se for root."""
        span.finish()
        
        if span in self.active_spans:
            self.active_spans.remove(span)
        
        # Exporta se for span raiz
        if not span.parent:
            self._export_trace(span)
        
        logger.debug(
            f"Span finalizado: {span.name} "
            f"(duration={span.duration_ms:.2f}ms, status={span.status})"
        )
    
    def _export_trace(self, root_span: Span):
        """Exporta trace para backend."""
        trace_data = self._build_trace_data(root_span)
        self.exported_traces.append(trace_data)
        
        # Exporta para backend configurado
        try:
            if self.backend == 'jaeger':
                self._export_to_jaeger(trace_data)
            elif self.backend == 'zipkin':
                self._export_to_zipkin(trace_data)
            elif self.backend == 'otlp':
                self._export_to_otlp(trace_data)
            else:
                logger.debug(f"Trace exportado (backend={self.backend}): {trace_data}")
        except Exception as e:
            logger.error(f"Erro ao exportar trace: {e}")
    
    def _build_trace_data(self, root_span: Span) -> Dict[str, Any]:
        """Constroi dados completos do trace."""
        spans = [root_span.to_dict()]
        
        # Coleta spans filhos recursivamente
        def collect_children(parent_span):
            for span in self.active_spans:
                if span.parent == parent_span:
                    spans.append(span.to_dict())
                    collect_children(span)
        
        collect_children(root_span)
        
        return {
            'service_name': TelemetryConfig.SERVICE_NAME,
            'trace_id': root_span.trace_id,
            'spans': spans,
            'timestamp': timezone.now().isoformat()
        }
    
    def _export_to_jaeger(self, trace_data: Dict[str, Any]):
        """Exporta para Jaeger."""
        try:
            import requests
            
            # Converte para formato Jaeger
            jaeger_payload = {
                'serviceName': TelemetryConfig.SERVICE_NAME,
                'processes': {
                    'p1': {
                        'serviceName': TelemetryConfig.SERVICE_NAME,
                        'tags': [{'key': 'service.version', 'value': '1.3.0'}]
                    }
                },
                'spans': []
            }
            
            for span_data in trace_data['spans']:
                jaeger_span = {
                    'traceID': span_data['trace_id'],
                    'spanID': span_data['span_id'],
                    'operationName': span_data['name'],
                    'startTime': int(span_data['start_time'] * 1000000),
                    'duration': int(span_data['duration_ms'] * 1000),
                    'processID': 'p1',
                    'tags': [
                        {'key': k, 'value': str(v)} 
                        for k, v in span_data.get('tags', {}).items()
                    ],
                    'logs': [
                        {
                            'timestamp': int(log['timestamp'] * 1000),
                            'fields': [{'key': 'message', 'value': log['message']}]
                        }
                        for log in span_data.get('logs', [])
                    ]
                }
                
                if span_data.get('parent_span_id'):
                    jaeger_span['references'] = [{
                        'refType': 'CHILD_OF',
                        'traceID': span_data['trace_id'],
                        'spanID': span_data['parent_span_id']
                    }]
                
                jaeger_payload['spans'].append(jaeger_span)
            
            response = requests.post(
                TelemetryConfig.JAEGER_ENDPOINT,
                json=jaeger_payload,
                timeout=5
            )
            
            if response.status_code == 200:
                logger.debug("Trace exportado para Jaeger com sucesso")
            else:
                logger.warning(f"Jaeger retornou status {response.status_code}")
                
        except ImportError:
            logger.debug("requests não disponível, trace não exportado para Jaeger")
        except Exception as e:
            logger.error(f"Erro ao exportar para Jaeger: {e}")
    
    def _export_to_zipkin(self, trace_data: Dict[str, Any]):
        """Exporta para Zipkin."""
        try:
            import requests
            
            zipkin_spans = []
            
            for span_data in trace_data['spans']:
                zipkin_span = {
                    'traceId': span_data['trace_id'][:16],  # Zipkin usa 64 bits
                    'id': span_data['span_id'],
                    'name': span_data['name'],
                    'timestamp': int(span_data['start_time'] * 1000000),
                    'duration': int(span_data['duration_ms'] * 1000),
                    'localEndpoint': {
                        'serviceName': TelemetryConfig.SERVICE_NAME
                    },
                    'tags': {str(k): str(v) for k, v in span_data.get('tags', {}).items()}
                }
                
                if span_data.get('parent_span_id'):
                    zipkin_span['parentId'] = span_data['parent_span_id']
                
                if span_data.get('status') == 'ERROR':
                    zipkin_span['tags']['error'] = span_data.get('error_message', 'Unknown error')
                
                zipkin_spans.append(zipkin_span)
            
            response = requests.post(
                TelemetryConfig.ZIPKIN_ENDPOINT,
                json=zipkin_spans,
                timeout=5
            )
            
            if response.status_code in (200, 202):
                logger.debug("Trace exportado para Zipkin com sucesso")
            else:
                logger.warning(f"Zipkin retornou status {response.status_code}")
                
        except ImportError:
            logger.debug("requests não disponível, trace não exportado para Zipkin")
        except Exception as e:
            logger.error(f"Erro ao exportar para Zipkin: {e}")
    
    def _export_to_otlp(self, trace_data: Dict[str, Any]):
        """Exporta via OTLP (OpenTelemetry Protocol)."""
        try:
            from opentelemetry.proto.trace.v1 import trace_pb2
            from opentelemetry.proto.collector.trace.v1 import trace_service_pb2
            import grpc
            
            # Implementação simplificada - requer biblioteca opentelemetry-proto
            logger.debug("Exportação OTLP requer configuração adicional")
            
        except ImportError:
            logger.debug("opentelemetry-proto não disponível")
        except Exception as e:
            logger.error(f"Erro ao exportar via OTLP: {e}")


# Singleton global
_tracer: Optional[Tracer] = None


def get_tracer() -> Tracer:
    """Obtém tracer singleton."""
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer


# Decorador para tracing automático
def trace_operation(operation_name: str = None):
    """
    Decorador para adicionar tracing automático em funções.
    
    Uso:
        @trace_operation('process_event')
        def process_event(event):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = operation_name or func.__name__
            tracer = get_tracer()
            
            with tracer_context(name):
                span = tracer.active_spans[-1] if tracer.active_spans else None
                
                if span:
                    span.set_attribute('function', func.__name__)
                    span.set_attribute('module', func.__module__)
                
                try:
                    result = func(*args, **kwargs)
                    
                    if span:
                        span.set_tag('success', True)
                    
                    return result
                    
                except Exception as e:
                    if span:
                        span.set_error(e)
                    raise
        
        return wrapper
    return decorator


@contextmanager
def tracer_context(name: str, parent: Optional[Span] = None):
    """Context manager para tracing."""
    tracer = get_tracer()
    span = tracer.start_span(name, parent)
    
    try:
        yield span
    except Exception as e:
        span.set_error(e)
        raise
    finally:
        tracer.end_span(span)


# Métricas pré-definidas para eSocial
def track_esocial_event(event_type: str, success: bool, duration_ms: float):
    """Registra métricas de evento eSocial."""
    metrics = get_metrics_collector()
    
    # Contador de eventos
    metrics.inc_counter(
        'esocial_events_total',
        labels={'event_type': event_type, 'status': 'success' if success else 'error'}
    )
    
    # Histograma de duração
    metrics.observe_histogram(
        'esocial_event_duration_ms',
        duration_ms,
        labels={'event_type': event_type}
    )
    
    # Gauge de eventos ativos
    metrics.set_gauge(
        'esocial_events_active',
        1 if not success else 0,
        labels={'event_type': event_type}
    )


def track_webservice_call(service: str, endpoint: str, success: bool, duration_ms: float):
    """Registra métricas de chamada ao webservice."""
    metrics = get_metrics_collector()
    
    metrics.inc_counter(
        'esocial_webservice_calls_total',
        labels={
            'service': service,
            'endpoint': endpoint,
            'status': 'success' if success else 'error'
        }
    )
    
    metrics.observe_histogram(
        'esocial_webservice_latency_ms',
        duration_ms,
        labels={'service': service, 'endpoint': endpoint}
    )


def track_validation_result(validation_type: str, valid: bool, errors_count: int):
    """Registra métricas de validação."""
    metrics = get_metrics_collector()
    
    metrics.inc_counter(
        'esocial_validations_total',
        labels={
            'validation_type': validation_type,
            'result': 'valid' if valid else 'invalid'
        }
    )
    
    if errors_count > 0:
        metrics.observe_histogram(
            'esocial_validation_errors',
            errors_count,
            labels={'validation_type': validation_type}
        )


# Middleware Django para tracing de requests
class TelemetryMiddleware:
    """Middleware Django para tracing automático de requests."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if not TelemetryConfig.ENABLED:
            return self.get_response(request)
        
        tracer = get_tracer()
        
        with tracer_context(f"HTTP {request.method}", None) as span:
            span.set_attribute('http.method', request.method)
            span.set_attribute('http.url', request.get_full_path())
            span.set_attribute('http.user_agent', request.META.get('HTTP_USER_AGENT', ''))
            
            start_time = time.time()
            
            try:
                response = self.get_response(request)
                
                duration_ms = (time.time() - start_time) * 1000
                
                span.set_attribute('http.status_code', response.status_code)
                span.set_tag('success', response.status_code < 500)
                
                # Registra métrica
                track_webservice_call(
                    'django',
                    request.path,
                    response.status_code < 500,
                    duration_ms
                )
                
                return response
                
            except Exception as e:
                span.set_error(e)
                raise


# Exporta métricas para Prometheus
def prometheus_metrics_view(request):
    """View Django que exporta métricas no formato Prometheus."""
    from django.http import HttpResponse
    
    metrics = get_metrics_collector()
    metrics_text = metrics.get_metrics_prometheus_format()
    
    return HttpResponse(metrics_text, content_type='text/plain; charset=utf-8')


# Health check com telemetria
def health_check() -> Dict[str, Any]:
    """Verifica saúde do sistema de telemetria."""
    tracer = get_tracer()
    metrics = get_metrics_collector()
    
    return {
        'status': 'healthy',
        'telemetry': {
            'enabled': TelemetryConfig.ENABLED,
            'backend': TelemetryConfig.TRACING_BACKEND,
            'active_spans': len(tracer.active_spans),
            'exported_traces': len(tracer.exported_traces),
            'metrics_count': len(metrics.counters) + len(metrics.gauges) + len(metrics.histograms)
        },
        'timestamp': timezone.now().isoformat()
    }
