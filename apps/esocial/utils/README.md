# Utils do eSocial

Módulos utilitários para profissionalização do sistema eSocial v1.3.

## Estrutura

```
utils/
├── __init__.py              # Exporta todas as funcionalidades
├── error_translator.py      # Tradução de erros técnicos → linguagem amigável
├── xml_validator.py         # Validação estrita contra XSD oficial
├── digital_signature.py     # Assinatura digital (A1 e A3)
└── webservice_client.py     # Comunicação SOAP com retry inteligente
```

## Funcionalidades

### 1. Tradutor de Erros (`error_translator.py`)

Traduz códigos e mensagens técnicas do eSocial em linguagem acessível:

```python
from apps.esocial.utils import translate_error, get_error_details

# Traduz por código
msg = translate_error(code="205")
# "Trabalhador não encontrado: Não há registro ativo para este CPF/NIS no sistema."

# Traduz por mensagem
msg = translate_error(message="Erro de validação: campo cpf inválido")
# "Documento pessoal: Verifique se o CPF está correto..."

# Extrai e traduz erros de XML de resposta
result = get_error_details(xml_response)
print(result['summary'])  # Resumo amigável de todos os erros
```

**Recursos:**
- Mapeamento de 40+ códigos de erro comuns
- Análise semântica automática de mensagens
- Sugestões de ação contextualizadas
- Suporte a múltiplos erros simultâneos

---

### 2. Validador XML (`xml_validator.py`)

Validação estrita contra schemas XSD oficiais da v1.3:

```python
from apps.esocial.utils import validate_xml, validate_file, EsocialXMLValidator

# Validação rápida
result = validate_xml(xml_content)

if result['valid']:
    print("✓ XML válido!")
else:
    for error in result['errors']:
        print(f"❌ Linha {error['line']}: {error['message']}")

# Validação de arquivo
result = validate_file('/path/to/evento.xml')

# Validador personalizado
validator = EsocialXMLValidator(version='v_S_01_03_00')
result = validator.validate_event(xml_content, event_type='evtAdmissao')
```

**Recursos:**
- Validação contra XSDs oficiais
- Cache de schemas para performance
- Detecção automática de tipo de evento
- Validação de lotes completos
- Relatório detalhado de erros (linha, coluna, tipo)

---

### 3. Assinatura Digital (`digital_signature.py`)

Assinatura XML-DSig com certificados A1 e A3:

```python
from apps.esocial.utils import CertificadoDigital, EsocialSigner, sign_xml

# Carrega certificado A1
cert = CertificadoDigital(
    cert_path='/path/to/certificado.pfx',
    password='senha123',
    cert_type='A1'
)

# Verifica validade
if cert.is_valid:
    print(f"Válido até: {cert.days_until_expiration} dias")
    print(f"CNPJ/CPF: {cert.subject_name}")

# Assina evento
signer = EsocialSigner(cert)
signed_xml = signer.sign_event(xml_content)

# Ou função rápida
signed_xml = sign_xml(xml_content, '/path/to/cert.pfx', 'senha')

# Verifica assinatura
from apps.esocial.utils import verify_signature
info = verify_signature(signed_xml)
print(f"Assinatura válida: {info['valid']}")
```

**Recursos:**
- Suporte a certificados A1 (.pfx/.p12)
- Preparado para A3 (PKCS#11)
- Verificação de validade temporal
- Extração de CNPJ/CPF do certificado
- Assinatura enveloped padrão eSocial
- Verificação de integridade

---

### 4. Cliente Webservice (`webservice_client.py`)

Comunicação SOAP com retry inteligente e tratamento de erros:

```python
from apps.esocial.utils import EsocialCommunication, send_to_esocial

# Cliente configurável
client = EsocialCommunication(
    environment='producao_restrita',  # ou 'producao'
    timeout=30,
    max_retries=3
)

# Envia lote assinado
result = client.send_batch(signed_xml)

if result['success']:
    print(f"✅ Enviado! Recibo: {result['recibo']}")
else:
    print(f"❌ Erro: {result['friendly_message']}")
    for error in result['errors']:
        print(f"  - {error['friendly_message']}")

# Ou função completa (valida + assina + envia)
result = send_to_esocial(
    xml_content=xml,
    cert_path='/path/to/cert.pfx',
    cert_password='senha',
    environment='producao_restrita'
)
```

**Recursos:**
- Retry com backoff exponencial (2s, 4s, 8s...)
- Timeout configurável
- Tradução automática de erros
- Logging estruturado de auditoria
- Extração automática de recibo
- Teste de conectividade

---

## Fluxo Completo Recomendado

```python
from apps.esocial.utils import (
    validate_xml,
    CertificadoDigital,
    EsocialSigner,
    EsocialCommunication,
    translate_error
)

def enviar_evento_esocial(xml_content, cert_path, cert_password):
    """Fluxo completo profissional."""
    
    # 1. Validação
    print("🔍 Validando XML...")
    validation = validate_xml(xml_content)
    
    if not validation['valid']:
        errors = [e['message'] for e in validation['errors']]
        return {
            'success': False,
            'stage': 'validacao',
            'errors': errors,
            'message': f"XML inválido: {', '.join(errors)}"
        }
    
    # 2. Assinatura
    print("✍️  Assinando...")
    try:
        cert = CertificadoDigital(cert_path, cert_password)
        
        if not cert.is_valid:
            return {
                'success': False,
                'stage': 'certificado',
                'message': f"Certificado inválido. Expira em {cert.days_until_expiration} dias."
            }
        
        signer = EsocialSigner(cert)
        signed_xml = signer.sign_event(xml_content)
        
    except Exception as e:
        return {
            'success': False,
            'stage': 'assinatura',
            'message': f"Erro na assinatura: {translate_error(message=str(e))}"
        }
    
    # 3. Envio
    print("📤 Enviando para eSocial...")
    client = EsocialCommunication(environment='producao_restrita')
    result = client.send_batch(signed_xml)
    
    return {
        'success': result['success'],
        'stage': 'envio',
        'recibo': result.get('recibo'),
        'message': result['friendly_message'],
        'duration': result['duration_seconds']
    }

# Uso
resultado = enviar_evento_esocial(xml, './cert.pfx', 'senha')

if resultado['success']:
    print(f"✅ Sucesso! {resultado['message']}")
else:
    print(f"❌ Falha na etapa {resultado['stage']}: {resultado['message']}")
```

---

## Configuração de Logging

Adicione ao `settings.py` ou configuração de logging:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'audit': {
            'format': 'AUDIT: {asctime} | {lote_id} | {success} | {recibo}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'audit_file': {
            'class': 'logging.FileHandler',
            'filename': 'logs/esocial_audit.log',
            'formatter': 'audit',
        },
    },
    'loggers': {
        'apps.esocial.utils': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'esocial.audit': {
            'handlers': ['audit_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

---

## Boas Práticas Implementadas

✅ **Validação local antes do envio** - Economiza tentativas falhas  
✅ **Retry inteligente** - Lida com instabilidade do eSocial  
✅ **Erros amigáveis** - Usuário entende o problema  
✅ **Logging de auditoria** - Rastreabilidade completa  
✅ **Certificado validity check** - Previne falhas por expiração  
✅ **Timeout configurável** - Evita esperas infinitas  
✅ **Separação de responsabilidades** - Código modular e testável  

---

## Próximas Melhorias Sugeridas

- [ ] Integração com HSM para certificados A3
- [ ] Consulta automática de situação de lote
- [ ] Webhook para notificação de processamento
- [ ] Dashboard de monitoramento de envios
- [ ] Cache de certificados em memória
- [ ] Suporte a múltiplos certificados (empresas diferentes)
