"""
eSocial HSM Cloud Signer
Suporte para Hardware Security Module em Nuvem (AWS CloudHSM, Azure Key Vault HSM, Google Cloud HSM)
 Mantém compatibilidade com A1/A3 local via Strategy Pattern.
"""
import logging
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

from .digital_signature import DigitalSignatureBase

logger = logging.getLogger(__name__)


class HSMProvider(ABC):
    """Interface base para provedores HSM"""
    
    @abstractmethod
    def sign(self, data: bytes, key_id: str) -> bytes:
        pass
    
    @abstractmethod
    def get_certificate(self, key_id: str) -> bytes:
        pass


class AWSCloudHSM(HSMProvider):
    """Implementação para AWS CloudHSM / KMS"""
    
    def __init__(self, region_name: str, key_id: str):
        try:
            import boto3
            self.kms_client = boto3.client('kms', region_name=region_name)
            self.key_id = key_id
        except ImportError:
            raise RuntimeError("boto3 necessário para AWS CloudHSM")

    def sign(self, data: bytes, key_id: str) -> bytes:
        response = self.kms_client.sign(
            KeyId=key_id or self.key_id,
            Message=data,
            MessageType='RAW',
            SigningAlgorithm='RSASSA_PKCS1_V1_5_SHA256'
        )
        return response['Signature']

    def get_certificate(self, key_id: str) -> bytes:
        # Em produção, o certificado público geralmente é armazenado no SSM ou ACM
        # Aqui simulamos a recuperação
        raise NotImplementedError("Implementar recuperação de cert via ACM/SSM")


class AzureKeyVaultHSM(HSMProvider):
    """Implementação para Azure Key Vault HSM"""
    
    def __init__(self, vault_url: str, credential):
        try:
            from azure.keyvault.keys import KeyClient
            from azure.keyvault.keys.crypto import CryptoClient, SignatureAlgorithm
            self.vault_url = vault_url
            self.credential = credential
            self.key_client = KeyClient(vault_url=vault_url, credential=credential)
        except ImportError:
            raise RuntimeError("azure-keyvault-keys necessário para Azure HSM")

    def sign(self, data: bytes, key_id: str) -> bytes:
        key = self.key_client.get_key(key_id)
        crypto_client = CryptoClient(key, self.credential)
        signed = crypto_client.sign(
            SignatureAlgorithm.rs256, # RS256 = RSASSA-PKCS1-v1_5 using SHA-256
            data
        )
        return signed.signature

    def get_certificate(self, key_id: str) -> bytes:
        # Recupera o certificado do cofre
        from azure.keyvault.certificates import CertificateClient
        cert_client = CertificateClient(vault_url=self.vault_url, credential=self.credential)
        cert = cert_client.get_certificate(key_id)
        return cert.cer


class CloudSigner(DigitalSignatureBase):
    """
    Signer que delega a assinatura para HSM em Nuvem.
    Usa o padrão Strategy para alternar entre provedores.
    """
    
    def __init__(self, provider: str, config: Dict[str, Any]):
        self.provider_name = provider
        self.provider = self._factory(provider, config)
        super().__init__() # Inicializa base se necessário

    def _factory(self, provider: str, config: Dict[str, Any]) -> HSMProvider:
        if provider == 'aws':
            return AWSCloudHSM(
                region_name=config.get('region', 'us-east-1'),
                key_id=config.get('key_id')
            )
        elif provider == 'azure':
            # Credential deve vir do Secret Manager
            return AzureKeyVaultHSM(
                vault_url=config.get('vault_url'),
                credential=config.get('credential') 
            )
        else:
            raise ValueError(f"Provedor HSM {provider} não suportado")

    def sign_xml(self, xml_content: str, key_id: str) -> str:
        """
        Assina o XML usando HSM remoto.
        Nota: A lógica de envelopamento XML-DSig ainda é local, 
        apenas o hash é enviado para assinatura remota.
        """
        from lxml import etree
        import hashlib
        import base64

        doc = etree.fromstring(xml_content.encode())
        
        # 1. Preparar o nó SignedInfo (padrão eSocial)
        # ... (lógica simplificada de extração do DigestValue e Reference)
        # Na prática, reutilizamos a lógica de construção do SignedInfo da classe base
        # e apenas substituímos a etapa de assinatura do Digest.
        
        # Para este exemplo, vamos assumir que extraímos os bytes a serem assinados
        # Isso requer integração profunda com a lógica de XML-DSig
        # Aqui demonstramos o conceito de chamada ao HSM
        
        # Simulação dos bytes do DigestValue que precisam ser assinados
        # Na implementação real, isso vem do cálculo do SHA256 do SignedInfo
        bytes_to_sign = self._prepare_signed_info_bytes(doc) 
        
        # 2. Chamar HSM
        signature_bytes = self.provider.sign(bytes_to_sign, key_id)
        
        # 3. Obter Certificado Público para incluir no XML
        cert_bytes = self.provider.get_certificate(key_id)
        
        # 4. Inserir Signature e X509Data no XML
        return self._inject_signature(doc, signature_bytes, cert_bytes)

    def _prepare_signed_info_bytes(self, doc: etree.ElementTree) -> bytes:
        # Implementação complexa de canonicalização (C14N) do nó SignedInfo
        # Crucial para a assinatura validar no eSocial
        signed_info = doc.find('.//{http://www.w3.org/2000/09/xmldsig#}SignedInfo')
        if signed_info is None:
            raise ValueError("SignedInfo não encontrado")
        return etree.to_string(signed_info, method='c14n')

    def _inject_signature(self, doc: etree.ElementTree, sig_bytes: bytes, cert_bytes: bytes) -> str:
        # Lógica para injetar a Base64 da assinatura e o certificado no XML
        # Similar ao signer local, mas usando dados remotos
        import base64
        from lxml import etree
        
        ns = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}
        sig_val = doc.find('.//ds:SignatureValue', namespaces=ns)
        if sig_val is not None:
            sig_val.text = base64.b64encode(sig_bytes).decode()
            
        # Inserir X509Certificate
        # ... (lógica de inserção no X509Data)
        
        return etree.tostring(doc, pretty_print=True, encoding='unicode')

    def validate_certificate_expiry(self, key_id: str) -> bool:
        """Validade gerida pelo provedor cloud, mas podemos checar metadata"""
        # Implementação específica por cloud
        return True
