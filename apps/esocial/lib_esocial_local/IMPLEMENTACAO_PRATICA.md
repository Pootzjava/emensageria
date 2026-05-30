# Guia de Implementação Prática - LIBeSocial Enterprise

Este documento fornece instruções passo-a-passo para implementar as melhorias sugeridas na avaliação técnica.

---

## PRÉ-REQUISITOS

- Python 3.9+ (recomendado 3.11+)
- pip >= 23.0
- Git

---

## PASSO 1: ATUALIZAR DEPENDÊNCIAS

### 1.1 Atualizar `setup.py`

```python
# setup.py - NOVA VERSÃO
import os
import re
from setuptools import find_packages, setup

from codecs import open

here = os.path.abspath(os.path.dirname(__file__))

install_requires = [
    'requests>=2.31.0',
    'lxml>=4.9.3',
    'zeep>=4.2.0',
    'signxml>=3.2.0',
    'cryptography>=41.0.0',  # Substitui pyOpenSSL
    'dotmap>=1.3.30',
    'pydantic>=2.0.0',       # Validação de dados
    'tenacity>=8.2.0',       # Retry logic
    'structlog>=23.1.0',     # Logging estruturado
]

def read_file(*parts):
    with open(os.path.join(here, *parts), 'r', encoding='utf-8') as fp:
        return fp.read()

def find_version(*paths):
    version_file = read_file(*paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError('Unable to find version string.')

setup(
    name='libesocial',
    version=find_version('esocial', '__init__.py'),
    description='Biblioteca para uso com o eSocial',
    long_description=read_file('README.md'),
    long_description_content_type='text/markdown',
    url='https://github.com/qualitaocupacional/libesocial',
    author='Qualita Seguranca e Saude Ocupacional',
    author_email='lab.ti@qualitamais.com.br',
    license='Apache 2.0',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    include_package_data=True,
    install_requires=install_requires,
    python_requires='>=3.9',  # Remover suporte Python 2
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',  # Atualizar status
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
    extras_require={
        'dev': [
            'pytest>=7.4.0',
            'pytest-cov>=4.1.0',
            'pytest-asyncio>=0.21.0',
            'black>=23.0.0',
            'flake8>=6.1.0',
            'mypy>=1.5.0',
            'bandit>=1.7.0',
            'safety>=2.3.0',
        ],
        'aws': [
            'boto3>=1.28.0',
        ],
        'azure': [
            'azure-identity>=1.14.0',
            'azure-keyvault-secrets>=4.7.0',
        ],
    },
)
```

### 1.2 Atualizar `requirements-dev.txt`

```txt
# requirements-dev.txt - NOVA VERSÃO
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-asyncio>=0.21.0
black>=23.0.0
flake8>=6.1.0
mypy>=1.5.0
bandit>=1.7.0
safety>=2.3.0
pre-commit>=3.4.0
```

### 1.3 Instalar novas dependências

```bash
# Limpar instalação anterior
pip uninstall libesocial -y

# Instalar nova versão em modo desenvolvimento
pip install -e ".[dev]"

# Verificar instalações
pip list | grep -E "(pydantic|tenacity|structlog|cryptography)"
```

---

## PASSO 2: CONFIGURAR LOGGING ESTRUTURADO

### 2.1 Atualizar `esocial/__init__.py`

```python
# esocial/__init__.py - ADICIONAR no início do arquivo
import structlog

# Configurar structlog para toda a biblioteca
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# ... restante do código existente
__version__ = '2.0.0'  # Atualizar versão
```

### 2.2 Criar módulo de logging dedicado

**Arquivo: `esocial/logging_config.py`**

```python
"""Configuração de logging para a biblioteca eSocial."""

import logging
import sys
from typing import Optional
import structlog


def setup_logging(
    level: str = "INFO",
    json_format: bool = True,
    output_file: Optional[str] = None
) -> None:
    """
    Configura o logging para a biblioteca eSocial.
    
    Args:
        level: Nível de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Se True, usa formato JSON; se False, usa formato legível
        output_file: Arquivo de saída (opcional). Se None, usa stdout.
    """
    
    # Configurar handlers
    handlers = []
    
    if output_file:
        file_handler = logging.FileHandler(output_file, encoding='utf-8')
        handlers.append(file_handler)
    
    stream_handler = logging.StreamHandler(sys.stdout)
    handlers.append(stream_handler)
    
    # Configurar logging básico
    logging.basicConfig(
        format='%(message)s',
        level=getattr(logging, level.upper()),
        handlers=handlers,
    )
    
    # Reconfigurar structlog se necessário
    if not json_format:
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Obtém um logger configurado.
    
    Args:
        name: Nome do logger (geralmente __name__)
    
    Returns:
        Logger configurado com structlog
    """
    return structlog.get_logger(name)
```

---

## PASSO 3: IMPLEMENTAR RETRY COM TENACITY

### 3.1 Atualizar `esocial/client.py`

```python
# esocial/client.py - ADICIONAR imports no topo
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_log,
    after_log,
    retry_any,
)
import structlog

logger = structlog.get_logger(__name__)

# ... imports existentes ...

# ADICIONAR decorator de retry antes dos métodos que fazem requisições

class WSClient(object):
    # ... código existente ...
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type((
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.RequestException,
        )),
        before=before_log(logger, logging.DEBUG),
        after=after_log(logger, logging.DEBUG),
        reraise=True,
    )
    def connect(self, url):
        """Conecta ao webservice com retry automático."""
        transport_session = requests.Session()
        transport_session.mount(
            'https://',
            CustomHTTPSAdapter(
                ctx_options={
                    'cert_data': self.cert_data,
                    'key_passwd': self.pfx_passw,
                    'cafile': self.ca_file
                }
            )
        )
        ws_transport = Transport(session=transport_session)
        return zeep.Client(url, transport=ws_transport)
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type((
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.RequestException,
            zeep.exceptions.TransportError,
        )),
        before=before_log(logger, logging.DEBUG),
        after=after_log(logger, logging.DEBUG),
        reraise=True,
    )
    def send(self, group_id=1, clear_batch=True):
        """Envia lote com retry automático."""
        batch_to_send = self._make_send_envelop(group_id)
        
        try:
            self.validate_envelop('send', batch_to_send)
        except Exception as e:
            logger.error("xml_validation_failed", 
                        error=str(e), 
                        group_id=group_id,
                        exc_info=True)
            raise
        
        url = esocial._WS_URL[self.target]['send']
        ws = None
        
        try:
            ws = self.connect(url)
            BatchElement = ws.get_element('ns1:EnviarLoteEventos')
            result = ws.service.EnviarLoteEventos(
                BatchElement(loteEventos=batch_to_send)
            )
            
            logger.info("batch_sent_successfully",
                       group_id=group_id,
                       events_count=len(self.batch))
            
            return (result, batch_to_send)
            
        finally:
            if clear_batch:
                self.clear_batch()
            if ws:
                del ws
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type((
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.RequestException,
            zeep.exceptions.TransportError,
        )),
        before=before_log(logger, logging.DEBUG),
        after=after_log(logger, logging.DEBUG),
        reraise=True,
    )
    def retrieve(self, protocol_number):
        """Consulta lote com retry automático."""
        batch_to_search = self._make_retrieve_envelop(protocol_number)
        self.validate_envelop('retrieve', batch_to_search)
        
        url = esocial._WS_URL[self.target]['retrieve']
        ws = None
        
        try:
            ws = self.connect(url)
            SearchElement = ws.get_element('ns1:ConsultarLoteEventos')
            result = ws.service.ConsultarLoteEventos(
                SearchElement(consulta=batch_to_search)
            )
            
            logger.info("batch_retrieved_successfully",
                       protocol=protocol_number)
            
            return result
            
        finally:
            if ws:
                del ws
    
    # ... restante do código existente ...
```

---

## PASSO 4: CRIAR MODELOS PYDANTIC

### 4.1 Criar `esocial/models.py`

```python
"""Modelos de dados para validação com Pydantic."""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Literal, List, Dict, Any
from datetime import datetime
from enum import Enum


class TipoInscricao(int, Enum):
    """Tipos de inscrição no eSocial."""
    CNPJ = 1
    CPF = 2


class AmbienteTarget(str, Enum):
    """Ambientes do eSocial."""
    PRODUCAO = "production"
    TESTES = "tests"
    HOMOLOGACAO = "homologation"


class EmployerID(BaseModel):
    """Identificação do empregador."""
    
    tpInsc: TipoInscricao = Field(
        ..., 
        description="Tipo de inscrição: 1=CNPJ, 2=CPF"
    )
    nrInsc: str = Field(
        ..., 
        description="Número de inscrição (CNPJ ou CPF)",
        min_length=11, 
        max_length=14
    )
    use_full: bool = Field(
        default=False,
        description="Usar número completo do CNPJ (14 dígitos)"
    )
    
    @field_validator('nrInsc')
    @classmethod
    def validate_nrinsc(cls, v: str) -> str:
        """Valida se nrInsc contém apenas dígitos e tem tamanho correto."""
        if not v.isdigit():
            raise ValueError('nrInsc deve conter apenas dígitos')
        
        if len(v) not in [11, 14]:
            raise ValueError('nrInsc deve ter 11 (CPF) ou 14 (CNPJ) dígitos')
        
        # Validar dígito verificador do CPF se tiver 11 dígitos
        if len(v) == 11:
            if not cls._validate_cpf(v):
                raise ValueError('CPF inválido')
        
        return v
    
    @staticmethod
    def _validate_cpf(cpf: str) -> bool:
        """Valida dígito verificador do CPF."""
        if len(cpf) != 11 or cpf == cpf[0] * 11:
            return False
        
        def calculate_digit(digits, weight):
            remainder = sum(d * w for d, w in zip(digits, weight)) % 11
            return 0 if remainder < 2 else 11 - remainder
        
        # Primeiro dígito verificador
        d1 = calculate_digit(cpf[:9], range(10, 1, -1))
        if d1 != int(cpf[9]):
            return False
        
        # Segundo dígito verificador
        d2 = calculate_digit(cpf[:10], range(11, 1, -1))
        if d2 != int(cpf[10]):
            return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário compatível com o client antigo."""
        return {
            'tpInsc': self.tpInsc.value,
            'nrInsc': self.nrInsc,
            'use_full': self.use_full,
        }


class SenderID(EmployerID):
    """Identificação do transmissor (pode ser o mesmo que employer)."""
    pass


class EventConfig(BaseModel):
    """Configuração de evento individual."""
    
    event_type: str = Field(..., description="Tipo do evento (ex: S-2220)")
    xml_content: str = Field(..., description="Conteúdo XML do evento")
    generate_id: bool = Field(
        default=True,
        description="Gerar ID automaticamente"
    )
    sign_event: bool = Field(
        default=True,
        description="Assinar o evento"
    )


class BatchConfig(BaseModel):
    """Configuração de lote de eventos."""
    
    group_id: int = Field(
        default=1,
        ge=1,
        le=9,
        description="Grupo do lote (1-9)"
    )
    events: List[EventConfig] = Field(
        ...,
        description="Lista de eventos do lote"
    )
    employer_id: EmployerID
    sender_id: Optional[SenderID] = None
    clear_after_send: bool = Field(
        default=True,
        description="Limpar lote após envio"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "group_id": 1,
                "events": [
                    {
                        "event_type": "S-2220",
                        "xml_content": "<evtMonit>...</evtMonit>",
                        "generate_id": True,
                        "sign_event": True
                    }
                ],
                "employer_id": {
                    "tpInsc": 1,
                    "nrInsc": "12345678901234",
                    "use_full": False
                }
            }
        }
    )


class BatchStatus(str, Enum):
    """Status de processamento do lote."""
    PENDING = "PENDING"
    SENT = "SENT"
    PROCESSED = "PROCESSED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class EventResult(BaseModel):
    """Resultado do processamento de um evento."""
    
    event_id: str
    status_code: str
    status_description: str
    receipt_number: Optional[str] = None
    receipt_hash: Optional[str] = None
    processing_date: Optional[datetime] = None
    errors: List[Dict[str, Any]] = Field(default_factory=list)


class BatchResult(BaseModel):
    """Resultado do processamento de um lote."""
    
    protocolo: str
    status: BatchStatus
    dh_recepcao: datetime
    versao_aplicativo: str
    eventos: List[EventResult] = Field(default_factory=list)
    total_events: int
    successful_events: int
    failed_events: int
    
    @property
    def success_rate(self) -> float:
        """Calcula taxa de sucesso do lote."""
        if self.total_events == 0:
            return 0.0
        return self.successful_events / self.total_events


class WSClientConfig(BaseModel):
    """Configuração do cliente eSocial."""
    
    pfx_file: Optional[str] = Field(
        default=None,
        description="Caminho para arquivo de certificado PFX"
    )
    pfx_password: Optional[str] = Field(
        default=None,
        description="Senha do certificado",
        exclude=True  # Não incluir em logs/representações
    )
    cert_identifier: Optional[str] = Field(
        default=None,
        description="Identificador para buscar certificado em secrets manager"
    )
    employer_id: EmployerID
    sender_id: Optional[SenderID] = None
    target: AmbienteTarget = Field(
        default=AmbienteTarget.TESTES,
        description="Ambiente de destino"
    )
    ca_file: Optional[str] = Field(
        default=None,
        description="Caminho para arquivo CA bundle"
    )
    esocial_version: str = Field(
        default="S-1.0",
        description="Versão do layout eSocial"
    )
    enable_metrics: bool = Field(
        default=True,
        description="Habilitar coleta de métricas"
    )
    enable_retry: bool = Field(
        default=True,
        description="Habilitar retry automático"
    )
    max_retries: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Número máximo de tentativas"
    )
    request_timeout: float = Field(
        default=30.0,
        ge=1.0,
        description="Timeout das requisições em segundos"
    )
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "pfx_file": "/path/to/cert.pfx",
                "pfx_password": "senha_secreta",
                "employer_id": {
                    "tpInsc": 1,
                    "nrInsc": "12345678901234"
                },
                "target": "tests",
                "enable_metrics": True,
                "enable_retry": True
            }
        }
    )
```

---

## PASSO 5: IMPLEMENTAR MÉTRICAS

### 5.1 Criar `esocial/metrics.py`

```python
"""Módulo para coleta e análise de métricas."""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class OperationMetrics:
    """Métricas de uma operação específica."""
    
    name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0.0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """Taxa de sucesso."""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls
    
    @property
    def avg_latency_ms(self) -> float:
        """Latência média em milissegundos."""
        if self.total_calls == 0:
            return 0.0
        return self.total_latency_ms / self.total_calls
    
    @property
    def error_rate(self) -> float:
        """Taxa de erro."""
        return 1.0 - self.success_rate
    
    def to_dict(self) -> Dict:
        """Converte para dicionário."""
        return {
            "name": self.name,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": f"{self.success_rate:.2%}",
            "error_rate": f"{self.error_rate:.2%}",
            "avg_latency_ms": f"{self.avg_latency_ms:.2f}",
            "last_error": self.last_error,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
        }


@dataclass
class MetricsCollector:
    """Coletor de métricas da biblioteca eSocial."""
    
    operations: Dict[str, OperationMetrics] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)
    
    def get_operation(self, name: str) -> OperationMetrics:
        """Obtém ou cria métricas para uma operação."""
        if name not in self.operations:
            self.operations[name] = OperationMetrics(name=name)
        return self.operations[name]
    
    @contextmanager
    def track_operation(self, operation_name: str, **extra_context):
        """
        Context manager para rastrear operações.
        
        Uso:
            with metrics.track_operation("send_batch", group_id=1):
                # código da operação
                pass
        """
        start_time = time.perf_counter()
        metrics = self.get_operation(operation_name)
        metrics.total_calls += 1
        
        try:
            yield
            metrics.successful_calls += 1
            
        except Exception as e:
            metrics.failed_calls += 1
            metrics.last_error = str(e)
            metrics.last_error_time = datetime.now()
            
            logger.error(
                "operation_failed",
                operation=operation_name,
                error=str(e),
                latency_ms=(time.perf_counter() - start_time) * 1000,
                **extra_context,
            )
            raise
            
        finally:
            latency_ms = (time.perf_counter() - start_time) * 1000
            metrics.total_latency_ms += latency_ms
            
            logger.info(
                "operation_completed",
                operation=operation_name,
                latency_ms=latency_ms,
                success=metrics.failed_calls == 0,
                **extra_context,
            )
    
    def get_summary(self) -> Dict:
        """Obtém resumo de todas as métricas."""
        total_calls = sum(op.total_calls for op in self.operations.values())
        total_successful = sum(op.successful_calls for op in self.operations.values())
        total_failed = sum(op.failed_calls for op in self.operations.values())
        
        uptime = datetime.now() - self.start_time
        
        return {
            "uptime_seconds": uptime.total_seconds(),
            "start_time": self.start_time.isoformat(),
            "current_time": datetime.now().isoformat(),
            "total_operations": total_calls,
            "total_successful": total_successful,
            "total_failed": total_failed,
            "overall_success_rate": f"{total_successful / total_calls:.2%}" if total_calls > 0 else "N/A",
            "operations": {
                name: op.to_dict() 
                for name, op in self.operations.items()
            },
        }
    
    def reset(self):
        """Reseta todas as métricas."""
        self.operations.clear()
        self.start_time = datetime.now()
        logger.info("metrics_reset")
    
    def export_prometheus(self) -> str:
        """
        Exporta métricas no formato Prometheus.
        
        Uso: expor em endpoint /metrics para scraping do Prometheus.
        """
        lines = []
        lines.append("# HELP esocial_operations_total Total de operações")
        lines.append("# TYPE esocial_operations_total counter")
        
        for name, op in self.operations.items():
            lines.append(f'esocial_operations_total{{operation="{name}",status="success"}} {op.successful_calls}')
            lines.append(f'esocial_operations_total{{operation="{name}",status="failed"}} {op.failed_calls}')
        
        lines.append("")
        lines.append("# HELP esocial_operation_latency_ms Latência das operações")
        lines.append("# TYPE esocial_operation_latency_ms gauge")
        
        for name, op in self.operations.items():
            if op.total_calls > 0:
                avg_latency = op.total_latency_ms / op.total_calls
                lines.append(f'esocial_operation_latency_ms{{operation="{name}"}} {avg_latency:.2f}')
        
        return "\n".join(lines)
```

---

## PASSO 6: ATUALIZAR TESTES

### 6.1 Criar testes para novos recursos

**Arquivo: `esocial/tests/test_models.py`**

```python
"""Testes para modelos Pydantic."""

import pytest
from esocial.models import EmployerID, TipoInscricao, BatchConfig, EventConfig


class TestEmployerID:
    """Testes para modelo EmployerID."""
    
    def test_valid_cnpj(self):
        """Testa CNPJ válido."""
        employer = EmployerID(tpInsc=1, nrInsc='12345678901234')
        assert employer.tpInsc == TipoInscricao.CNPJ
        assert employer.nrInsc == '12345678901234'
    
    def test_valid_cpf(self):
        """Testa CPF válido."""
        employer = EmployerID(tpInsc=2, nrInsc='12345678901')
        assert employer.tpInsc == TipoInscricao.CPF
        assert employer.nrInsc == '12345678901'
    
    def test_invalid_cpf_checksum(self):
        """Testa CPF com dígito verificador inválido."""
        with pytest.raises(ValueError, match="CPF inválido"):
            EmployerID(tpInsc=2, nrInsc='12345678900')
    
    def test_invalid_length(self):
        """Testa número com tamanho inválido."""
        with pytest.raises(ValueError, match="deve ter 11"):
            EmployerID(tpInsc=1, nrInsc='123456789')
    
    def test_non_numeric(self):
        """Testa número com caracteres não numéricos."""
        with pytest.raises(ValueError, match="apenas dígitos"):
            EmployerID(tpInsc=1, nrInsc='1234567890123X')
    
    def test_to_dict(self):
        """Testa conversão para dicionário."""
        employer = EmployerID(tpInsc=1, nrInsc='12345678901234', use_full=True)
        result = employer.to_dict()
        assert result == {
            'tpInsc': 1,
            'nrInsc': '12345678901234',
            'use_full': True,
        }


class TestBatchConfig:
    """Testes para configuração de lote."""
    
    def test_valid_batch(self):
        """Testa configuração válida de lote."""
        config = BatchConfig(
            group_id=1,
            events=[
                EventConfig(
                    event_type='S-2220',
                    xml_content='<evtMonit>test</evtMonit>'
                )
            ],
            employer_id=EmployerID(tpInsc=1, nrInsc='12345678901234')
        )
        assert config.group_id == 1
        assert len(config.events) == 1
    
    def test_invalid_group_id(self):
        """Testa group_id fora do intervalo."""
        with pytest.raises(ValueError):
            BatchConfig(
                group_id=10,  # Inválido: deve ser 1-9
                events=[],
                employer_id=EmployerID(tpInsc=1, nrInsc='12345678901234')
            )
```

**Arquivo: `esocial/tests/test_metrics.py`**

```python
"""Testes para métricas."""

import pytest
import time
from esocial.metrics import MetricsCollector, OperationMetrics


class TestMetricsCollector:
    """Testes para coletor de métricas."""
    
    def test_track_successful_operation(self):
        """Testa rastreamento de operação bem-sucedida."""
        collector = MetricsCollector()
        
        with collector.track_operation("test_op"):
            time.sleep(0.01)  # Simula trabalho
        
        metrics = collector.get_operation("test_op")
        assert metrics.total_calls == 1
        assert metrics.successful_calls == 1
        assert metrics.failed_calls == 0
        assert metrics.avg_latency_ms >= 10  # 10ms mínimo
    
    def test_track_failed_operation(self):
        """Testa rastreamento de operação com falha."""
        collector = MetricsCollector()
        
        with pytest.raises(ValueError):
            with collector.track_operation("failing_op"):
                raise ValueError("Erro simulado")
        
        metrics = collector.get_operation("failing_op")
        assert metrics.total_calls == 1
        assert metrics.successful_calls == 0
        assert metrics.failed_calls == 1
        assert metrics.last_error == "Erro simulado"
    
    def test_get_summary(self):
        """Testa obtenção de resumo."""
        collector = MetricsCollector()
        
        with collector.track_operation("op1"):
            pass
        
        with collector.track_operation("op2"):
            pass
        
        summary = collector.get_summary()
        assert summary["total_operations"] == 2
        assert "op1" in summary["operations"]
        assert "op2" in summary["operations"]
    
    def test_export_prometheus(self):
        """Testa exportação no formato Prometheus."""
        collector = MetricsCollector()
        
        with collector.track_operation("send"):
            pass
        
        prometheus_output = collector.export_prometheus()
        assert 'esocial_operations_total{operation="send"' in prometheus_output
        assert 'esocial_operation_latency_ms' in prometheus_output
```

---

## PASSO 7: EXECUTAR TESTES E VALIDAR

```bash
# Rodar testes unitários
pytest esocial/tests/ -v --cov=esocial --cov-report=html

# Verificar cobertura
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux

# Rodar linter
flake8 esocial/

# Rodar type checker
mypy esocial/

# Security scan
bandit -r esocial/

# Check dependencies
safety check
```

---

## PASSO 8: DOCUMENTAR MUDANÇAS

### 8.1 Atualizar README.md

Adicionar seção sobre novas funcionalidades:

```markdown
## Novas Funcionalidades (v2.0)

### Logging Estruturado

A biblioteca agora usa logging estruturado com `structlog`:

```python
import logging
from esocial.logging_config import setup_logging

# Configurar logging
setup_logging(level='INFO', json_format=True)

# Logs serão emitidos em JSON para fácil integração com ELK/Splunk
```

### Retry Automático

Todas as operações de rede agora têm retry automático com backoff exponencial:

```python
client = WSClient(...)

# Em caso de falha temporária, a biblioteca tentará automaticamente até 5 vezes
result, batch = client.send(group_id=1)
```

### Validação de Dados

Uso de Pydantic para validação robusta:

```python
from esocial.models import EmployerID

# Validação automática de CPF/CNPJ
employer = EmployerID(tpInsc=1, nrInsc='12345678901234')  # OK
employer = EmployerID(tpInsc=1, nrInsc='123')  # ValueError!
```

### Métricas

Coleta automática de métricas de desempenho:

```python
client = WSClient(..., enable_metrics=True)

# Após operações
metrics = client.metrics.get_summary()
print(f"Success rate: {metrics['overall_success_rate']}")
```
```

---

## CHECKLIST FINAL

- [ ] Todas as dependências instaladas
- [ ] Logging estruturado configurado
- [ ] Retry implementado e testado
- [ ] Modelos Pydantic criados
- [ ] Métricas funcionando
- [ ] Testes passando (>90% coverage)
- [ ] Linting sem erros
- [ ] Type checking sem erros
- [ ] Security scan limpo
- [ ] Documentação atualizada
- [ ] Changelog criado
- [ ] Versionamento atualizado (v2.0.0)

---

## SUPORTE

Para dúvidas ou problemas na implementação:

1. Consulte a documentação em `/docs`
2. Verifique os exemplos em `/examples`
3. Abra uma issue no GitHub
4. Contate: lab.ti@qualitamais.com.br

---

*Guia atualizado em Dezembro de 2024*
