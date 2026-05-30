# 🚀 eSocial Enterprise v1.3 - Documentação Completa

## Visão Geral

Sistema eSocial completamente refatorado para atender à versão 1.3 do layout, com funcionalidades **enterprise de nível elite** que elevam o projeto muito acima da média.

---

## 📋 Índice

1. [Arquitetura](#arquitetura)
2. [Funcionalidades Implementadas](#funcionalidades-implementadas)
3. [Instalação e Configuração](#instalação-e-configuração)
4. [Módulos Principais](#módulos-principais)
5. [API REST](#api-rest)
6. [Fluxos Operacionais](#fluxos-operacionais)
7. [Monitoramento e Observabilidade](#monitoramento-e-observabilidade)
8. [Segurança](#segurança)
9. [Testes](#testes)
10. [Deploy em Produção](#deploy-em-produção)
11. [Solução de Problemas](#solução-de-problemas)

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                    eSocial Enterprise v1.3                   │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   API REST  │  │  Dashboard  │  │  Webhooks   │         │
│  │   (DRF)     │  │  (Stats)    │  │  (Events)   │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                 │
│  ┌──────▼────────────────▼────────────────▼──────┐         │
│  │           Camada de Serviços (Utils)          │         │
│  │  ┌─────────────────────────────────────────┐  │         │
│  │  │ • Error Translator (mensagens amigáveis)│  │         │
│  │  │ • XML Validator (XSD oficial v1.3)      │  │         │
│  │  │ • Digital Signature (A1/A3)             │  │         │
│  │  │ • WebService Client (retry inteligente) │  │         │
│  │  │ • Secret Manager (Zero Trust)           │  │         │
│  │  │ • Rule Engine (regras dinâmicas)        │  │         │
│  │  │ • Dry Run (simulação segura)            │  │         │
│  │  │ • Telemetry (OpenTelemetry)             │  │         │
│  │  └─────────────────────────────────────────┘  │         │
│  └───────────────────────────────────────────────┘         │
│         │                                                   │
│  ┌──────▼──────────────────────────────────────┐           │
│  │        Processamento Assíncrono (Celery)    │           │
│  │  • Validação de eventos                     │           │
│  │  • Assinatura digital                       │           │
│  │  • Envio ao governo                         │           │
│  │  • Notificações webhook                     │           │
│  └─────────────────────────────────────────────┘           │
│         │                                                   │
│  ┌──────▼──────────────────────────────────────┐           │
│  │              Banco de Dados                 │           │
│  │  • Eventos                                  │           │
│  │  • Lotes                                    │           │
│  │  • Recibos                                  │           │
│  │  • Webhook Subscriptions                    │           │
│  └─────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

---

## ✅ Funcionalidades Implementadas

### Core eSocial v1.3
- [x] 52 XSDs oficiais baixados e instalados
- [x] 65 templates HTML para todos os eventos
- [x] Validação estrita contra schemas oficiais
- [x] Assinatura digital PKCS#12 (A1) e PKCS#11 (A3)

### Módulos Profissionais
- [x] **Error Translator**: 40+ códigos de erro traduzidos
- [x] **XML Validator**: Validação local com cache
- [x] **Digital Signature**: Certificados A1/A3 com validade
- [x] **WebService Client**: Retry com backoff exponencial

### Camada Enterprise
- [x] **API REST**: 12 endpoints documentados
- [x] **Processamento Assíncrono**: 4 tasks Celery
- [x] **Dashboard**: Métricas em tempo real
- [x] **Webhooks**: Notificações automáticas seguras

### Nível Elite
- [x] **Secret Manager**: AWS Secrets Manager, HashiCorp Vault, Azure Key Vault
- [x] **Rule Engine**: Regras de negócio dinâmicas via JSON/DB
- [x] **Dry Run**: Simulação completa sem envio real
- [x] **Compliance Tests**: Suite de testes com mutação de XML
- [x] **Telemetry**: OpenTelemetry, Jaeger, Zipkin, Prometheus

---

## 🛠️ Instalação e Configuração

### Pré-requisitos

```bash
Python 3.9+
Django 3.2+
PostgreSQL 13+
Redis (para Celery)
Certificado Digital eSocial (A1 ou A3)
```

### Instalação das Dependências

```bash
pip install -r requirements.txt

# Dependências enterprise adicionais
pip install boto3 hvac azure-identity azure-keyvault opentelemetry-api
```

### Configuração de Variáveis de Ambiente

```bash
# .env.example atualizado

# eSocial
VERSAO_LAYOUT_ESOCIAL=v_S_01_03_00
ESOCIAL_AMBIENTE=producao_restrita
ESOCIAL_CNPJ_EMPREGADOR=12345678000199

# Certificado Digital (Zero Trust - use Secret Manager em produção)
ESOCIAL_CERT_PATH=/path/to/cert.pfx
ESOCIAL_CERT_PASSWORD=sua_senha

# Secret Manager (habilitar em produção)
AWS_SECRET_MANAGER_ENABLED=true
AWS_REGION=us-east-1
VAULT_ENABLED=false
VAULT_ADDR=http://localhost:8200
AZURE_KEY_VAULT_ENABLED=false

# Rule Engine
ESOCIAL_RULES_FROM_DB=true
ESOCIAL_RULES_JSON_PATH=/path/to/rules.json

# Telemetry
ESOCIAL_TELEMETRY_ENABLED=true
ESOCIAL_TRACING_BACKEND=jaeger
JAEGER_ENDPOINT=http://localhost:14268/api/traces
ESOCIAL_METRICS_ENABLED=true

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Migrações do Banco de Dados

```bash
python manage.py makemigrations esocial
python manage.py migrate
```

### Coleta de Arquivos Estáticos

```bash
python manage.py collectstatic --noinput
```

---

## 📦 Módulos Principais

### 1. Secret Manager (Zero Trust)

**Localização:** `apps/esocial/utils/secret_manager.py`

Gerencia credenciais sensíveis de forma segura, suportando múltiplos provedores:

```python
from apps.esocial.utils.secret_manager import get_secret, get_certificate

# Obter certificado do eSocial
cert_data = get_certificate('esocial_cert')
cert_password = get_secret('esocial_cert_password')

# Obter credenciais de serviço
db_creds = get_secret_manager().get_credentials('database')
```

**Provedores Suportados:**
- AWS Secrets Manager
- HashiCorp Vault
- Azure Key Vault
- Variáveis de Ambiente (fallback)

### 2. Rule Engine (Regras Dinâmicas)

**Localização:** `apps/esocial/utils/rule_engine.py`

Motor de regras que permite atualizar validações sem deploy:

```python
from apps.esocial.utils.rule_engine import validate_event, get_rule_engine

# Validar dados de evento
result = validate_event('S-2200', {
    'cpf': '12345678901',
    'dt_nascimento': '1990-01-01'
})

if not result['valid']:
    for error in result['errors']:
        print(f"Erro: {error['message']}")

# Adicionar nova regra via JSON
nova_regra = '''
{
    "rule_id": "EMPRESA_SALARIO_MINIMO",
    "name": "Salário mínimo da empresa",
    "event_type": "S-2200",
    "conditions": [
        {"field": "remuneracao.salario", "operator": "gte", "value": 1500.00}
    ]
}
'''
from apps.esocial.utils.rule_engine import register_rule_from_json
register_rule_from_json(nova_regra)
```

### 3. Dry Run (Simulação Segura)

**Localização:** `apps/esocial/utils/dry_run.py`

Simula todo o fluxo de envio sem transmitir dados ao governo:

```python
from apps.esocial.utils.dry_run import dry_run

# Simular envio de evento
resultado = dry_run(
    event_type='S-2200',
    event_data={
        'cpf': '12345678901',
        'nome': 'João da Silva',
        'dt_nascimento': '1990-01-01'
    },
    cert_path='/path/to/cert.pfx',
    cert_password='senha'
)

print(resultado['report'])  # Relatório detalhado
```

**Etapas Simuladas:**
1. Validação de regras de negócio
2. Geração do XML
3. Validação contra XSD
4. Assinatura digital
5. Simulação de transmissão

### 4. Compliance Tests

**Localização:** `apps/esocial/tests/compliance_tests.py`

Suite de testes que valida o validador local:

```bash
# Executar testes de conformidade
python apps/esocial/tests/compliance_tests.py

# Ou via Django
python manage.py test apps.esocial.tests.compliance_tests
```

**Tipos de Mutações Testadas:**
- CPF/CNPJ com tamanho inválido
- Datas futuras
- Campos obrigatórios ausentes
- XML malformado
- Namespace inválido

### 5. Telemetry (Observabilidade)

**Localização:** `apps/esocial/utils/telemetry.py`

Rastreamento distribuído e métricas:

```python
from apps.esocial.utils.telemetry import (
    tracer_context, 
    track_esocial_event,
    trace_operation
)

# Tracing manual
with tracer_context('processar_lote'):
    # Seu código aqui
    pass

# Decorador automático
@trace_operation('enviar_evento')
def enviar_evento(evento):
    ...

# Métricas
track_esocial_event(
    event_type='S-2200',
    success=True,
    duration_ms=1234.5
)
```

**Backends Suportados:**
- Jaeger
- Zipkin
- OTLP (OpenTelemetry Protocol)

**Métricas Exportadas (Prometheus):**
- `esocial_events_total`
- `esocial_event_duration_ms`
- `esocial_webservice_calls_total`
- `esocial_validations_total`

---

## 🔌 API REST

### Endpoints Disponíveis

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/esocial/v1/events/` | Listar eventos |
| POST | `/api/esocial/v1/events/` | Criar evento |
| GET | `/api/esocial/v1/events/{id}/` | Detalhar evento |
| POST | `/api/esocial/v1/events/{id}/validate/` | Validar evento |
| POST | `/api/esocial/v1/events/{id}/send/` | Enviar evento |
| POST | `/api/esocial/v1/batches/` | Criar lote |
| POST | `/api/esocial/v1/batches/{id}/send/` | Enviar lote |
| GET | `/api/esocial/v1/receipts/` | Listar recibos |
| POST | `/api/esocial/v1/dry-run/` | Simular envio |
| GET | `/api/esocial/v1/stats/` | Estatísticas |
| GET | `/api/esocial/v1/health/` | Health check |
| GET | `/api/esocial/v1/metrics/` | Métricas Prometheus |

### Exemplo de Uso

```bash
# Criar evento S-2200
curl -X POST http://localhost:8000/api/esocial/v1/events/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "event_type": "S-2200",
    "data": {
      "cpf": "12345678901",
      "nome": "João da Silva",
      "dt_nascimento": "1990-01-01"
    }
  }'

# Validar evento
curl -X POST http://localhost:8000/api/esocial/v1/events/123/validate/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Simular envio (Dry Run)
curl -X POST http://localhost:8000/api/esocial/v1/dry-run/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "event_type": "S-2200",
    "event_data": {...},
    "cert_path": "/path/to/cert.pfx",
    "cert_password": "senha"
  }'

# Enviar evento (assíncrono via Celery)
curl -X POST http://localhost:8000/api/esocial/v1/events/123/send/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 🔄 Fluxos Operacionais

### Fluxo Completo de Envio

```
1. Criação do Evento (API)
   ↓
2. Validação de Regras (Rule Engine)
   ↓
3. Dry Run (Opcional mas recomendado)
   ↓
4. Geração do XML (Template v1.3)
   ↓
5. Validação XSD (XML Validator)
   ↓
6. Assinatura Digital (Digital Signature)
   ↓
7. Envio Assíncrono (Celery Task)
   ↓
8. Recebimento do Recibo
   ↓
9. Notificação Webhook (se configurado)
   ↓
10. Logging e Métricas (Telemetry)
```

### Task Celery - Envio de Evento

```python
from apps.esocial.tasks import send_event_to_esocial

# Envia evento assincronamente
task = send_event_to_esocial.delay(event_id=123)

# Monitorar progresso
task.status  # 'PENDING', 'STARTED', 'SUCCESS', 'FAILURE'
task.result  # Resultado após conclusão
```

---

## 📊 Monitoramento e Observabilidade

### Dashboard de Métricas

Acesse `/api/esocial/v1/stats/` para ver:
- Total de eventos por tipo
- Taxa de sucesso/falha
- Tempo médio de processamento
- Eventos pendentes
- Últimos erros

### Integração com Grafana

Configure datasource Prometheus apontando para:
```
http://seu-servidor:9090/api/esocial/v1/metrics/
```

**Dashboards Recomendados:**
- Visão geral de eventos
- Latência de envio
- Erros por tipo
- Utilização de certificados

### Rastreamento com Jaeger

1. Inicie Jaeger:
```bash
docker run -d -p 14268:14268 -p 16686:16686 jaegertracing/all-in-one
```

2. Acesse UI em `http://localhost:16686`

3. Busque traces por:
   - Service name: `esocial-enterprise`
   - Operation name: `HTTP POST`, `send_event`, etc.

---

## 🔒 Segurança

### Zero Trust com Secret Manager

**Nunca armazene certificados no disco em produção!**

Configuração recomendada:

```bash
# AWS Secrets Manager
aws secretsmanager create-secret \
  --name esocial/prod/cert \
  --secret-string file://cert.pfx

# HashiCorp Vault
vault kv put secret/esocial/cert data=@cert.pfx
```

No código:
```python
# Obtém certificado sem tocar no filesystem
cert = get_certificate('esocial_cert')
```

### Validação de Certificados

O sistema verifica automaticamente:
- Data de validade
- Cadeia de confiança
- Revogação (CRL/OCSP)

### Webhooks Seguros

Todos os webhooks usam HMAC-SHA256:

```python
# Verificar assinatura no receptor
import hmac
import hashlib

expected_signature = hmac.new(
    secret.encode(),
    request.body,
    hashlib.sha256
).hexdigest()

assert request.headers['X-Hub-Signature'] == expected_signature
```

---

## 🧪 Testes

### Executar Todos os Testes

```bash
# Testes unitários
python manage.py test apps.esocial

# Testes de conformidade
python apps/esocial/tests/compliance_tests.py

# Com coverage
coverage run --source='apps/esocial' manage.py test
coverage report
coverage html
```

### Testes de Integração eSocial

```bash
# Ambiente de homologação
export ESOCIAL_AMBIENTE=homologacao
python manage.py test apps.esocial.tests.integration
```

---

## 🚀 Deploy em Produção

### Checklist de Deploy

- [ ] Variáveis de ambiente configuradas
- [ ] Secret Manager habilitado
- [ ] Certificado válido instalado
- [ ] Banco de dados migrado
- [ ] Redis configurado para Celery
- [ ] Workers Celery rodando
- [ ] Telemetry configurado (Jaeger/Prometheus)
- [ ] Webhooks testados
- [ ] Backup automatizado configurado
- [ ] Monitoramento ativo

### Docker Compose (Produção)

```yaml
version: '3.8'

services:
  web:
    build: .
    command: gunicorn config.wsgi:application --bind 0.0.0.0:8000
    env_file: .env.production
    depends_on:
      - db
      - redis
  
  celery:
    build: .
    command: celery -A config worker --loglevel=info
    env_file: .env.production
    depends_on:
      - db
      - redis
  
  celery-beat:
    build: .
    command: celery -A config beat --loglevel=info
    env_file: .env.production
  
  redis:
    image: redis:7-alpine
  
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: esocial
      POSTGRES_USER: esocial
      POSTGRES_PASSWORD: ${DB_PASSWORD}
  
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"
  
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
```

---

## 🔧 Solução de Problemas

### Erro: Certificado Expirado

```python
from apps.esocial.utils.digital_signature import DigitalSignature

signer = DigitalSignature('/path/to/cert.pfx', 'senha')
info = signer.get_certificate_info()

print(info['not_after'])  # Data de expiração
print(info['valid'])      # False se expirado
```

**Solução:** Renovar certificado e atualizar no Secret Manager.

### Erro: Validação XSD Falhando

1. Verifique versão do layout:
```bash
echo $VERSAO_LAYOUT_ESOCIAL  # Deve ser v_S_01_03_00
```

2. Valide manualmente:
```python
from apps.esocial.utils.xml_validator import XMLValidator

validator = XMLValidator()
result = validator.validate_file('/path/to/event.xml')
print(result['errors'])
```

### Erro: Timeout no Envio

O sistema já implementa retry automático. Se persistir:

1. Verifique logs do Celery
2. Ajuste timeout em `.env`:
```bash
ESOCIAL_WEBSERVICE_TIMEOUT=60  # segundos
```

3. Monitore no Jaeger para identificar gargalos

### Erro: Webhook Não Recebendo

1. Verifique subscription:
```bash
curl http://localhost:8000/api/esocial/v1/webhooks/
```

2. Teste endpoint manualmente:
```bash
curl -X POST https://seu-sistema.com/webhook \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
```

3. Verifique logs de entrega:
```python
from apps.esocial.models import WebhookDelivery
WebhookDelivery.objects.filter(success=False).order_by('-created_at')[:10]
```

---

## 📞 Suporte

### Logs

```bash
# Logs da aplicação
tail -f /var/log/esocial/app.log

# Logs do Celery
tail -f /var/log/esocial/celery.log

# Logs de auditoria
tail -f /var/log/esocial/audit.log
```

### Contato

- Documentação oficial eSocial: https://www.gov.br/esocial/pt-br/documentacao-tecnica
- Canal de suporte: suporte@empresa.com
- Issue tracker: https://github.com/empresa/esocial-enterprise/issues

---

## 📄 Licença

Proprietário - Todos os direitos reservados.

---

**Versão:** 1.3.0  
**Última atualização:** 2024  
**Status:** ✅ Produção
