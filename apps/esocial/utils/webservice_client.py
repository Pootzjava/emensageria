"""
Módulo de comunicação com o webservice do eSocial.
Implementa envio SOAP com retry inteligente, logging estruturado e tratamento de erros.
"""

from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import time
import logging
import hashlib

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_result
)

logger = logging.getLogger(__name__)


class EsocialWebServiceError(Exception):
    """Exceção personalizada para erros do webservice do eSocial."""
    
    def __init__(self, message: str, code: Optional[str] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.code = code
        self.response_data = response_data or {}


class EsocialCommunication:
    """
    Cliente de comunicação com o webservice do eSocial.
    Implementa padrões de retry, logging e tratamento de erros.
    """
    
    # URLs dos ambientes
    ENVIRONMENTS = {
        'producao_restrita': {
            'url': 'https://prepro.esocial.gov.br/service/v1_03_00/EnviarLoteEventos',
            'name': 'Produção Restrita'
        },
        'producao': {
            'url': 'https://servicos.esocial.gov.br/service/v1_03_00/EnviarLoteEventos',
            'name': 'Produção'
        },
        'desenvolvimento': {
            'url': 'https://prepro.esocial.gov.br/service/v1_03_00/EnviarLoteEventos',
            'name': 'Desenvolvimento'
        }
    }
    
    def __init__(
        self,
        environment: str = 'producao_restrita',
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Inicializa o cliente de comunicação.
        
        Args:
            environment: Ambiente ('producao_restrita', 'producao', 'desenvolvimento')
            timeout: Timeout em segundos para requisições
            max_retries: Número máximo de tentativas de retry
        """
        if environment not in self.ENVIRONMENTS:
            raise ValueError(f"Ambiente inválido: {environment}. Opções: {list(self.ENVIRONMENTS.keys())}")
        
        self.environment = environment
        self.service_url = self.ENVIRONMENTS[environment]['url']
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Session reutilizável para melhor performance
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'text/xml;charset=UTF-8',
            'SOAPAction': '',
            'Accept': 'application/xml'
        })
        
        # Configura retry decorator
        self._send_with_retry = retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=60),
            retry=(
                retry_if_exception_type(requests.exceptions.Timeout) |
                retry_if_exception_type(requests.exceptions.ConnectionError) |
                retry_if_result(self._should_retry_response)
            ),
            reraise=True
        )(self._send_request_raw)
    
    def _should_retry_response(self, response: requests.Response) -> bool:
        """Determina se a resposta deve triggering um retry."""
        if response is None:
            return True
        
        # Retry em erros 5xx do servidor
        if 500 <= response.status_code < 600:
            logger.warning(f"Erro {response.status_code} - Tentando novamente...")
            return True
        
        # Não retry em erros de cliente (4xx)
        return False
    
    def _send_request_raw(self, xml_content: str) -> requests.Response:
        """Envia requisição SOAP bruta (sem retry)."""
        headers = {
            'Content-Type': 'text/xml;charset=UTF-8',
            'SOAPAction': '',
            'Accept': 'application/xml'
        }
        
        logger.debug(f"Enviando para {self.service_url}")
        logger.debug(f"Payload size: {len(xml_content)} bytes")
        
        try:
            response = self.session.post(
                self.service_url,
                data=xml_content.encode('utf-8'),
                headers=headers,
                timeout=self.timeout
            )
            
            logger.debug(f"Status code: {response.status_code}")
            logger.debug(f"Response size: {len(response.content)} bytes")
            
            return response
            
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout após {self.timeout}s: {str(e)}")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Erro de conexão: {str(e)}")
            raise
    
    def send_batch(
        self,
        xml_content: str,
        lote_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Envia um lote de eventos para o eSocial.
        
        Args:
            xml_content: XML do lote assinado
            lote_id: ID do lote (gerado automaticamente se não fornecido)
            
        Returns:
            Dicionário com resultado do envio:
            {
                'success': bool,
                'lote_id': str,
                'recibo': str (se sucesso),
                'errors': list (se erro),
                'friendly_message': str,
                'raw_response': str
            }
        """
        from .error_translator import EsocialErrorTranslator, get_error_details
        
        start_time = datetime.now()
        
        # Gera ID do lote se não fornecido
        if not lote_id:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            hash_content = hashlib.md5(xml_content.encode()).hexdigest()[:8]
            lote_id = f"LOTE_{timestamp}_{hash_content}"
        
        logger.info(f"Iniciando envio do lote {lote_id}")
        logger.info(f"Ambiente: {self.ENVIRONMENTS[self.environment]['name']}")
        
        result = {
            'success': False,
            'lote_id': lote_id,
            'recibo': None,
            'errors': [],
            'friendly_message': '',
            'raw_response': '',
            'status_code': None,
            'duration_seconds': 0
        }
        
        try:
            # Envia com retry
            response = self._send_with_retry(xml_content)
            
            result['raw_response'] = response.text
            result['status_code'] = response.status_code
            
            # Parse da resposta
            if response.status_code == 200:
                # Tenta extrair recibo
                recibo = self._extract_receipt(response.text)
                
                if recibo:
                    result['success'] = True
                    result['recibo'] = recibo
                    result['friendly_message'] = f"Lote enviado com sucesso! Recibo: {recibo}"
                    logger.info(f"Lote {lote_id} enviado com sucesso. Recibo: {recibo}")
                else:
                    # Resposta 200 mas sem recibo - pode ter erros de validação
                    error_details = get_error_details(response.text)
                    
                    if error_details['has_errors']:
                        result['errors'] = error_details['errors']
                        result['friendly_message'] = error_details['summary']
                        logger.warning(f"Lote {lote_id} processado com erros: {error_details['summary']}")
                    else:
                        result['success'] = True
                        result['friendly_message'] = "Lote processado com sucesso"
                        logger.info(f"Lote {lote_id} processado com sucesso")
            else:
                # Erro HTTP
                error_details = get_error_details(response.text)
                
                if error_details['has_errors']:
                    result['errors'] = error_details['errors']
                    result['friendly_message'] = error_details['summary']
                else:
                    # Traduz código HTTP
                    http_errors = {
                        401: "Erro de autenticação. Verifique o certificado digital.",
                        403: "Acesso negado. Verifique permissões no eSocial.",
                        404: "Serviço não encontrado. Verifique URL e ambiente.",
                        500: "Erro interno no servidor do eSocial.",
                        503: "Serviço temporariamente indisponível."
                    }
                    
                    result['friendly_message'] = http_errors.get(
                        response.status_code,
                        f"Erro na comunicação (código {response.status_code})"
                    )
                
                logger.error(f"Erro no envio do lote {lote_id}: {result['friendly_message']}")
                
        except Exception as e:
            logger.exception(f"Exceção no envio do lote {lote_id}: {str(e)}")
            
            result['friendly_message'] = f"Falha na comunicação: {str(e)}"
            
            # Tenta traduzir a exceção
            if isinstance(e, requests.exceptions.Timeout):
                result['friendly_message'] = (
                    "Tempo de resposta excedido. O eSocial pode estar sobrecarregado. "
                    "Tente novamente em alguns minutos."
                )
            elif isinstance(e, requests.exceptions.ConnectionError):
                result['friendly_message'] = (
                    "Erro de conexão. Verifique sua internet e tente novamente."
                )
        
        result['duration_seconds'] = (datetime.now() - start_time).total_seconds()
        
        # Log de auditoria
        self._log_audit(lote_id, result)
        
        return result
    
    def _extract_receipt(self, xml_response: str) -> Optional[str]:
        """Extrai número do recibo da resposta XML."""
        from lxml import etree
        
        try:
            root = etree.fromstring(xml_response.encode('utf-8'))
            
            # Namespaces possíveis
            namespaces = [
                {'ns': 'http://www.esocial.gov.br/schema/lote/eventos/v_S_01_03_00'},
                {'ns': 'http://www.esocial.gov.br/servicos/empregador/lote/eventos/envio/v1_03_00'}
            ]
            
            for ns in namespaces:
                # Tenta diferentes caminhos para o recibo
                paths = [
                    './/ns:retornoLote/ns:recibo',
                    './/ns:recibo',
                    './/{*}recibo'
                ]
                
                for path in paths:
                    elem = root.xpath(path, namespaces=ns)
                    if elem and elem[0].text:
                        return elem[0].text.strip()
            
            return None
            
        except Exception as e:
            logger.debug(f"Erro ao extrair recibo: {str(e)}")
            return None
    
    def _log_audit(self, lote_id: str, result: Dict):
        """Registra log de auditoria do envio."""
        audit_logger = logging.getLogger('esocial.audit')
        
        audit_logger.info(
            "AUDIT_SEND",
            extra={
                'lote_id': lote_id,
                'environment': self.environment,
                'success': result['success'],
                'recibo': result['recibo'],
                'error_count': len(result.get('errors', [])),
                'duration': result['duration_seconds'],
                'timestamp': datetime.now().isoformat()
            }
        )
    
    def check_status(self, protocolo: str) -> Dict[str, Any]:
        """
        Consulta situação de um lote já enviado.
        
        Args:
            protocolo: Número do protocolo/recibo do lote
            
        Returns:
            Situação do lote
        """
        # Implementação futura - depende do endpoint de consulta
        logger.info(f"Consulta de status para protocolo {protocolo}")
        
        return {
            'protocolo': protocolo,
            'status': 'nao_implementado',
            'message': 'Funcionalidade de consulta será implementada em breve'
        }
    
    def test_connection(self) -> bool:
        """Testa conectividade com o webservice."""
        try:
            response = self.session.get(
                self.service_url.replace('EnviarLoteEventos', ''),
                timeout=10
            )
            return response.status_code in [200, 404, 405]
        except Exception as e:
            logger.error(f"Teste de conexão falhou: {str(e)}")
            return False


# Função utilitária rápida
def send_to_esocial(
    xml_content: str,
    cert_path: str,
    cert_password: str,
    environment: str = 'producao_restrita'
) -> Dict:
    """
    Função completa de envio: valida, assina e envia.
    
    Args:
        xml_content: XML do evento ou lote
        cert_path: Caminho do certificado .pfx
        cert_password: Senha do certificado
        environment: Ambiente de destino
        
    Returns:
        Resultado completo do envio
    """
    from .xml_validator import validate_xml
    from .digital_signature import sign_xml, EsocialSigner, CertificadoDigital
    
    # 1. Valida XML
    validation_result = validate_xml(xml_content)
    
    if not validation_result.get('valid', False):
        return {
            'success': False,
            'stage': 'validation',
            'errors': validation_result.get('errors', []),
            'friendly_message': 'Erro de validação XML. Verifique os detalhes.'
        }
    
    # 2. Assina XML
    try:
        cert = CertificadoDigital(cert_path=cert_path, password=cert_password)
        signer = EsocialSigner(cert)
        signed_xml = signer.sign_event(xml_content)
    except Exception as e:
        return {
            'success': False,
            'stage': 'signature',
            'errors': [{'message': str(e)}],
            'friendly_message': f'Erro na assinatura digital: {str(e)}'
        }
    
    # 3. Envia
    communicator = EsocialCommunication(environment=environment)
    return communicator.send_batch(signed_xml)
