"""
Utils do eSocial - Módulo de utilitários profissionais.

Este pacote fornece funcionalidades robustas para:
- Validação XML contra XSD oficial
- Assinatura digital (A1/A3)
- Tradução de erros técnicos
- Comunicação SOAP com retry inteligente
"""

from .error_translator import (
    EsocialErrorTranslator,
    translate_error,
    get_error_details
)

from .xml_validator import (
    EsocialXMLValidator,
    validate_xml,
    validate_file
)

from .digital_signature import (
    CertificadoDigital,
    EsocialSigner,
    sign_xml,
    verify_signature
)

from .webservice_client import (
    EsocialCommunication,
    send_to_esocial,
    EsocialWebServiceError
)

__all__ = [
    # Error translator
    'EsocialErrorTranslator',
    'translate_error',
    'get_error_details',
    
    # XML Validator
    'EsocialXMLValidator',
    'validate_xml',
    'validate_file',
    
    # Digital signature
    'CertificadoDigital',
    'EsocialSigner',
    'sign_xml',
    'verify_signature',
    
    # Webservice client
    'EsocialCommunication',
    'send_to_esocial',
    'EsocialWebServiceError',
]

__version__ = '1.3.0'
__author__ = 'eSocial Professional Utils'
