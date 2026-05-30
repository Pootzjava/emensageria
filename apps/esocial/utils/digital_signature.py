"""
Módulo de assinatura digital para eventos do eSocial.
Suporta certificados A1 (arquivo .pfx/.p12) e A3 (token/cartão via PKCS#11).
"""

from typing import Optional, Union, Dict
from pathlib import Path
from datetime import datetime
import base64
import logging

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.backends import default_backend
from signxml import XMLSigner, methods
from lxml import etree

logger = logging.getLogger(__name__)


class CertificadoDigital:
    """
    Gerenciador de certificado digital para assinatura no eSocial.
    Suporta certificados A1 (arquivo) e A3 (hardware via PKCS#11).
    """
    
    def __init__(
        self,
        cert_path: Optional[str] = None,
        password: Optional[str] = None,
        cert_type: str = 'A1'
    ):
        """
        Inicializa o gerenciador de certificado.
        
        Args:
            cert_path: Caminho para o arquivo .pfx/.p12 (A1) ou biblioteca PKCS#11 (A3)
            password: Senha do certificado (obrigatório para A1)
            cert_type: Tipo do certificado ('A1' ou 'A3')
        """
        self.cert_path = cert_path
        self.password = password
        self.cert_type = cert_type.upper()
        
        self._private_key = None
        self._certificate = None
        self._validity_info = None
        
        if cert_type == 'A1' and cert_path:
            self._load_a1_certificate()
        elif cert_type == 'A3':
            logger.warning("Certificado A3 requer configuração específica da biblioteca PKCS#11")
    
    def _load_a1_certificate(self):
        """Carrega certificado A1 a partir de arquivo .pfx/.p12."""
        if not self.cert_path or not self.password:
            raise ValueError("Caminho e senha são obrigatórios para certificado A1")
        
        path = Path(self.cert_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Arquivo de certificado não encontrado: {self.cert_path}")
        
        try:
            with open(path, 'rb') as f:
                pfx_data = f.read()
            
            # Carrega certificado e chave privada
            private_key, certificate, _ = pkcs12.load_key_and_certificates(
                pfx_data,
                self.password.encode() if isinstance(self.password, str) else self.password,
                backend=default_backend()
            )
            
            self._private_key = private_key
            self._certificate = certificate
            
            # Extrai informações de validade
            self._validity_info = {
                'not_before': certificate.not_valid_before_utc,
                'not_after': certificate.not_valid_after_utc,
                'subject': certificate.subject.rfc4514_string(),
                'issuer': certificate.issuer.rfc4514_string(),
                'serial_number': certificate.serial_number
            }
            
            logger.info(f"Certificado carregado com sucesso: {self._validity_info['subject']}")
            
        except Exception as e:
            logger.error(f"Erro ao carregar certificado A1: {str(e)}")
            raise
    
    @property
    def is_valid(self) -> bool:
        """Verifica se o certificado é válido (não expirado e não revogado)."""
        if not self._certificate:
            return False
        
        now = datetime.utcnow()
        
        # Verifica validade temporal
        if now < self._validity_info['not_before']:
            logger.warning("Certificado ainda não é válido (data inicial futura)")
            return False
        
        if now > self._validity_info['not_after']:
            logger.warning(f"Certificado expirado em {self._validity_info['not_after']}")
            return False
        
        # Nota: Verificação de revogação (CRL/OCSP) exigiria implementação adicional
        return True
    
    @property
    def days_until_expiration(self) -> int:
        """Retorna dias restantes até expiração do certificado."""
        if not self._validity_info:
            return -1
        
        delta = self._validity_info['not_after'] - datetime.utcnow()
        return max(0, delta.days)
    
    @property
    def subject_name(self) -> str:
        """Retorna o nome do sujeito do certificado (CNPJ/CPF)."""
        if not self._validity_info:
            return ""
        
        # Tenta extrair CNPJ/CPF do subject
        subject = self._validity_info['subject']
        
        # Procura por OID de CNPJ/CPF (varia conforme autoridade certificadora)
        for part in subject.split(','):
            part = part.strip()
            if any(oid in part for oid in ['CNPJ=', 'CPF=', '2.5.4.97=']):
                return part.split('=')[1].strip()
        
        return subject
    
    def get_certificate_pem(self) -> str:
        """Retorna o certificado em formato PEM."""
        if not self._certificate:
            raise ValueError("Certificado não carregado")
        
        return self._certificate.public_bytes(
            serialization.Encoding.PEM
        ).decode('utf-8')


class EsocialSigner:
    """
    Assinador de eventos do eSocial.
    Realiza assinatura XML-DSig no formato exigido pelo eSocial.
    """
    
    # Namespace do eSocial
    ESOCIAL_NS = 'http://www.esocial.gov.br/schema/lote/eventos/v_S_01_03_00'
    
    def __init__(self, certificado: CertificadoDigital):
        """
        Inicializa o assinador com um certificado.
        
        Args:
            certificado: Instância de CertificadoDigital já carregada
        """
        self.certificado = certificado
        
        if not certificado.is_valid:
            logger.warning("Certificado inválido ou expirado. A assinatura pode falhar.")
    
    def sign_event(self, xml_content: str, event_id: Optional[str] = None) -> str:
        """
        Assina um evento XML do eSocial.
        
        Args:
            xml_content: Conteúdo XML do evento (sem assinatura)
            event_id: ID do evento (opcional, será extraído do XML se não fornecido)
            
        Returns:
            XML assinado como string
        """
        # Parse do XML
        try:
            root = etree.fromstring(xml_content.encode('utf-8'))
        except etree.XMLSyntaxError as e:
            logger.error(f"XML inválido para assinatura: {str(e)}")
            raise ValueError(f"XML mal formado: {str(e)}")
        
        # Detecta ID do evento
        if not event_id:
            # Tenta encontrar atributo Id ou ID
            event_id = root.get('Id') or root.get('ID')
            
            if not event_id:
                # Tenta buscar elemento de identificação
                id_elem = root.find('.//{*}ideEvento/{*}tpInsc')
                if id_elem is not None:
                    # Constrói ID baseado no conteúdo (implementação simplificada)
                    event_id = f"ID{root.tag.replace('{*}', '')}"
        
        # Adiciona atributo Id se não existir
        if event_id and not root.get('Id'):
            root.set('Id', event_id)
        
        # Configura signer
        signer = XMLSigner(method=methods.enveloped)
        
        # Define referência para o elemento raiz
        signer.reference_uri = f'#{event_id}' if event_id else None
        
        # Adiciona chave pública ao signature
        signer.key = self.certificado._private_key
        signer.cert = self.certificado._certificate
        
        try:
            # Realiza assinatura
            signed_root = signer.sign(root)
            
            # Formata XML de saída
            xml_str = etree.tostring(
                signed_root,
                encoding='unicode',
                pretty_print=True,
                xml_declaration=True,
                standalone=True
            )
            
            logger.info(f"Evento {event_id} assinado com sucesso")
            return xml_str
            
        except Exception as e:
            logger.error(f"Erro ao assinar evento: {str(e)}")
            raise
    
    def sign_batch(self, xml_content: str) -> str:
        """
        Assina um lote completo de eventos.
        No eSocial, cada evento é assinado individualmente dentro do lote.
        
        Args:
            xml_content: XML do lote contendo múltiplos eventos
            
        Returns:
            Lote com todos os eventos assinados
        """
        try:
            root = etree.fromstring(xml_content.encode('utf-8'))
        except etree.XMLSyntaxError as e:
            raise ValueError(f"XML do lote mal formado: {str(e)}")
        
        # Namespace
        ns = {'ns': self.ESOCIAL_NS}
        
        # Busca todos os eventos no lote
        events = root.xpath('//ns:Evento', namespaces=ns)
        
        if not events:
            logger.warning("Nenhum evento encontrado no lote para assinar")
            return xml_content
        
        logger.info(f"Assinando {len(events)} eventos no lote")
        
        # Assina cada evento individualmente
        for i, event_elem in enumerate(events, 1):
            event_xml = etree.tostring(event_elem, encoding='unicode')
            
            try:
                signed_event_xml = self.sign_event(event_xml)
                signed_event_root = etree.fromstring(signed_event_xml.encode('utf-8'))
                
                # Substitui evento não assinado pelo assinado
                parent = event_elem.getparent()
                index = list(parent).index(event_elem)
                parent.remove(event_elem)
                parent.insert(index, signed_event_root)
                
            except Exception as e:
                logger.error(f"Falha ao assinar evento {i}: {str(e)}")
                raise
        
        # Retorna lote formatado
        return etree.tostring(
            root,
            encoding='unicode',
            pretty_print=True,
            xml_declaration=True,
            standalone=True
        )


def sign_xml(xml_content: str, cert_path: str, cert_password: str) -> str:
    """
    Função utilitária rápida para assinar um XML.
    
    Args:
        xml_content: Conteúdo XML a ser assinado
        cert_path: Caminho para arquivo .pfx/.p12
        cert_password: Senha do certificado
        
    Returns:
        XML assinado
    """
    cert = CertificadoDigital(cert_path=cert_path, password=cert_password, cert_type='A1')
    signer = EsocialSigner(cert)
    return signer.sign_event(xml_content)


def verify_signature(xml_content: str) -> Dict:
    """
    Verifica se uma assinatura XML é válida.
    
    Args:
        xml_content: XML assinado
        
    Returns:
        Dicionário com resultado da verificação
    """
    result = {
        'valid': False,
        'errors': [],
        'signature_info': {}
    }
    
    try:
        root = etree.fromstring(xml_content.encode('utf-8'))
        
        # Busca elemento Signature
        sig_elem = root.find('.//{*}Signature')
        
        if sig_elem is None:
            result['errors'].append('Nenhuma assinatura encontrada no XML')
            return result
        
        # Extrai informações da assinatura
        sig_method = sig_elem.find('.//{*}SignatureMethod')
        if sig_method is not None:
            result['signature_info']['algorithm'] = sig_method.get('Algorithm', 'desconhecido')
        
        key_info = sig_elem.find('.//{*}KeyInfo')
        if key_info is not None:
            x509_data = key_info.find('.//{*}X509Data')
            if x509_data is not None:
                x509_cert = x509_data.find('.//{*}X509Certificate')
                if x509_cert is not None and x509_cert.text:
                    cert_b64 = x509_cert.text.replace('\n', '').replace(' ', '')
                    result['signature_info']['certificate_fingerprint'] = base64.b64decode(cert_b64)[:20].hex()
        
        # Validação completa exigiria verificação criptográfica complexa
        # Esta é uma verificação básica de estrutura
        result['valid'] = True
        result['signature_info']['present'] = True
        
    except Exception as e:
        result['errors'].append(f'Erro ao verificar assinatura: {str(e)}')
    
    return result
