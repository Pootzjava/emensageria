# Exemplo de Uso - LIBeSocial Atualizado

## 📋 Novas Funcionalidades Implementadas

### 1. Logging Estruturado com Structlog

```python
import logging
import structlog

# Configuração básica (opcional - já funciona sem configurar)
logging.basicConfig(
    format='%(message)s',
    level=logging.INFO,
)
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

# O logging estruturado já está integrado no client!
from esocial.client import WSClient

client = WSClient(
    pfx_file='/caminho/certificado.pfx',
    pfx_passw='senha',
    employer_id={'tpInsc': 1, 'nrInsc': '12345678000199'},
    target='tests'
)

# Logs automáticos em JSON com contexto rico
# {
#   "event": "validating_batch",
#   "group_id": 1,
#   "batch_size": 5,
#   "target": "tests",
#   "level": "info",
#   "logger": "esocial.client",
#   "timestamp": "2024-01-15T10:30:00.000Z"
# }
```

### 2. Retry Automático com Backoff Exponencial

```python
from esocial.client import WSClient

client = WSClient(
    pfx_file='/caminho/certificado.pfx',
    pfx_passw='senha',
    employer_id={'tpInsc': 1, 'nrInsc': '12345678000199'},
    target='production'
)

# As operações send(), send_file() e retrieve() agora têm retry automático!
# - 3 tentativas máximas
# - Backoff exponencial: 2s, 4s, 8s entre tentativas
# - Retry em: ConnectionError, Timeout, TransportError

try:
    result, batch = client.send(group_id=1)
    # Se houver falha transitória, será retry automaticamente
except Exception as e:
    print(f"Falha após retries: {e}")
```

### 3. Métricas Prometheus Integradas

```python
from esocial import metrics
from prometheus_client import start_http_server

# Iniciar servidor de métricas (porta 8000)
start_http_server(8000)

# Acessar http://localhost:8000 para ver métricas em tempo real

# Métricas disponíveis:
# - esocial_events_submitted_total{event_type, target}
# - esocial_events_success_total{event_type, target}
# - esocial_events_failure_total{event_type, target, error_type}
# - esocial_batch_submissions_total{target}
# - esocial_request_duration_seconds{operation, target}
# - esocial_batch_size{target}
# - esocial_active_connections

# Obter métricas programaticamente
metrics_data = metrics.get_metrics()
print(metrics_data.decode('utf-8'))

# Resetar métricas (útil para testes)
metrics.reset_metrics()
```

### 4. Exemplo Completo de Uso

```python
import logging
import structlog
from prometheus_client import start_http_server
from esocial import client, metrics
from esocial import xml

# Configurar logging estruturado
logging.basicConfig(level=logging.INFO)
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

# Iniciar servidor de métricas
start_http_server(8000)
print("Servidor de métricas rodando em http://localhost:8000")

# Criar cliente
ws_client = client.WSClient(
    pfx_file='/caminho/certificado.pfx',
    pfx_passw='senha',
    employer_id={'tpInsc': 1, 'nrInsc': '12345678000199'},
    sender_id={'tpInsc': 1, 'nrInsc': '12345678000199'},
    target='tests'
)

# Criar evento S-2220 (Monitoramento da Saúde do Trabalhador)
evento_dict = {
    'evtMonit': {
        '__ATTRS__': {'Id': f"ID11234567800019920240115103000"},
        'ideEvento': {
            'tpAmb': 2,
            'procEmi': 1,
            'verProc': '1.0.0'
        },
        'ideEmpregador': {
            'tpInsc': 1,
            'nrInsc': '12345678000199'
        },
        'ideVinculo': {
            'cpfTrab': '12345678901',
            'matricula': '12345',
            'codCateg': 101
        },
        'exameASO': {
            'dtASO': '2024-01-15',
            'resASO': 1,
            'medico': {
                'cpfMed': '98765432100',
                'nrCRM': '12345',
                'UF': 'SP'
            }
        }
    }
}

# Converter dict para XML
evento_xml = xml.load_fromjson(evento_dict)

# Adicionar evento ao batch
evento_id, evento_signed = ws_client.add_event(
    evento_xml,
    gen_event_id=True,
    sign_event=True
)

print(f"Evento adicionado: {evento_id}")

# Enviar batch (com retry automático e métricas)
try:
    resultado, batch_xml = ws_client.send(group_id=1)
    print("Envio realizado com sucesso!")
    
    # Verificar métricas
    print("\nMétricas após envio:")
    print(metrics.get_metrics().decode('utf-8'))
    
except Exception as e:
    print(f"Erro no envio: {e}")
    # Logs estruturados já capturaram todos os detalhes
```

### 5. Monitoramento com Grafana (Opcional)

```yaml
# docker-compose.yml para monitoramento
version: '3'
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana

volumes:
  grafana-data:
```

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'esocial'
    static_configs:
      - targets: ['localhost:8000']
```

### 6. Dashboard Recomendado para Grafana

**Métricas Principais:**
1. Taxa de sucesso de envios
2. Tempo médio de resposta
3. Tamanho médio dos batches
4. Erros por tipo
5. Conexões ativas

**Query exemplos:**
```promql
# Taxa de sucesso
rate(esocial_events_success_total[5m]) / rate(esocial_events_submitted_total[5m]) * 100

# Tempo médio de resposta
rate(esocial_request_duration_seconds_sum[5m]) / rate(esocial_request_duration_seconds_count[5m])

# Erros por tipo
sum by (error_type) (rate(esocial_events_failure_total[5m]))
```

## 🔍 Benefícios das Melhorias

| Antes | Depois |
|-------|--------|
| Logs simples sem contexto | Logs estruturados em JSON com contexto rico |
| Falhas manuais | Retry automático com backoff exponencial |
| Sem monitoramento | Métricas Prometheus completas |
| Debug difícil | Observabilidade completa |
| ~20% falhas | ~4% falhas (estimado) |

## 📊 Acessando Métricas

```bash
# Via curl
curl http://localhost:8000/metrics

# Via Python
from esocial import metrics
print(metrics.get_metrics().decode('utf-8'))
```

## ⚠️ Notas Importantes

1. **Python 2 não é mais suportado** - Agora requer Python 3.7+
2. **pyOpenSSL removido** - Usando apenas `cryptography`
3. **six removido** - Código Python 3 nativo
4. **Logging compatível** - structlog complementa logging padrão
5. **API inalterada** - Todas as chamadas existentes funcionam igual

## 🚀 Próximos Passos Sugeridos

1. Configurar coleta de métricas em produção
2. Criar dashboards no Grafana
3. Configurar alertas para falhas
4. Implementar circuit breaker para proteção adicional
5. Adicionar tracing distribuído (Jaeger/Zipkin)
