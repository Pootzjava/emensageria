"""
eSocial Secret Manager - Gestão de Segredos Zero Trust
Suporte para AWS Secrets Manager, HashiCorp Vault, Azure Key Vault
e fallback seguro para variáveis de ambiente.
"""

import os
import logging
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class SecretProvider(ABC):
    """Classe base para provedores de segredos."""
    
    @abstractmethod
    def get_secret(self, secret_name: str) -> Optional[str]:
        """Obtém um segredo pelo nome."""
        pass
    
    @abstractmethod
    def get_certificate(self, cert_name: str) -> Optional[bytes]:
        """Obtém um certificado (arquivo binário)."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Verifica se o provedor está disponível."""
        pass


class EnvironmentSecretProvider(SecretProvider):
    """Provedor de fallback usando variáveis de ambiente."""
    
    def __init__(self, prefix: str = "ESOCIAL_"):
        self.prefix = prefix
    
    def get_secret(self, secret_name: str) -> Optional[str]:
        env_name = f"{self.prefix}{secret_name.upper()}"
        value = os.getenv(env_name)
        if value:
            logger.debug(f"Segredo '{secret_name}' obtido do ambiente")
        return value
    
    def get_certificate(self, cert_name: str) -> Optional[bytes]:
        env_name = f"{self.prefix}CERT_{cert_name.upper()}"
        # Tenta como path primeiro
        cert_path = os.getenv(env_name)
        if cert_path and os.path.exists(cert_path):
            with open(cert_path, 'rb') as f:
                logger.debug(f"Certificado '{cert_name}' carregado de {cert_path}")
                return f.read()
        
        # Tenta como conteúdo base64
        cert_content = os.getenv(f"{env_name}_CONTENT")
        if cert_content:
            import base64
            try:
                logger.debug(f"Certificado '{cert_name}' decodificado de base64")
                return base64.b64decode(cert_content)
            except Exception as e:
                logger.error(f"Erro ao decodificar certificado: {e}")
        
        return None
    
    def is_available(self) -> bool:
        return True


class AWSSecretsManagerProvider(SecretProvider):
    """Provedor AWS Secrets Manager."""
    
    def __init__(self, region_name: str = None):
        self.region_name = region_name or os.getenv('AWS_REGION', 'us-east-1')
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client(
                    'secretsmanager',
                    region_name=self.region_name
                )
                logger.info("Cliente AWS Secrets Manager inicializado")
            except ImportError:
                logger.warning("boto3 não instalado. AWS Secrets Manager indisponível.")
                return None
            except Exception as e:
                logger.error(f"Erro ao inicializar AWS Secrets Manager: {e}")
                return None
        return self._client
    
    def get_secret(self, secret_name: str) -> Optional[str]:
        if not self.client:
            return None
        
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            
            if 'SecretString' in response:
                import json
                try:
                    secret_data = json.loads(response['SecretString'])
                    # Se for JSON, retorna o valor completo ou procura por chaves específicas
                    if isinstance(secret_data, dict):
                        return secret_data.get('value') or response['SecretString']
                    return response['SecretString']
                except json.JSONDecodeError:
                    return response['SecretString']
            
            if 'SecretBinary' in response:
                import base64
                return base64.b64decode(response['SecretBinary']).decode('utf-8')
                
        except Exception as e:
            logger.error(f"Erro ao obter segredo '{secret_name}': {e}")
            return None
        
        return None
    
    def get_certificate(self, cert_name: str) -> Optional[bytes]:
        secret_value = self.get_secret(cert_name)
        if secret_value:
            # Tenta como path
            if os.path.exists(secret_value):
                with open(secret_value, 'rb') as f:
                    return f.read()
            
            # Retorna como conteúdo direto (assume que já é o certificado)
            return secret_value.encode('utf-8')
        
        return None
    
    def is_available(self) -> bool:
        return self.client is not None


class VaultProvider(SecretProvider):
    """Provedor HashiCorp Vault."""
    
    def __init__(self, url: str = None, token: str = None, mount_point: str = "secret"):
        self.url = url or os.getenv('VAULT_ADDR', 'http://localhost:8200')
        self.token = token or os.getenv('VAULT_TOKEN')
        self.mount_point = mount_point
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            try:
                import hvac
                self._client = hvac.Client(
                    url=self.url,
                    token=self.token
                )
                if not self._client.is_authenticated():
                    logger.warning("Vault não autenticado")
                    return None
                logger.info("Cliente HashiCorp Vault inicializado")
            except ImportError:
                logger.warning("hvac não instalado. Vault indisponível.")
                return None
            except Exception as e:
                logger.error(f"Erro ao inicializar Vault: {e}")
                return None
        return self._client
    
    def get_secret(self, secret_name: str) -> Optional[str]:
        if not self.client:
            return None
        
        try:
            # Vault KV v2
            response = self.client.secrets.kv.v2.read_secret_version(
                path=secret_name,
                mount_point=self.mount_point
            )
            data = response.get('data', {}).get('data', {})
            
            # Retorna o valor ou converte dicionário para JSON
            if isinstance(data, dict):
                import json
                if 'value' in data:
                    return data['value']
                return json.dumps(data)
            
            return str(data)
            
        except Exception as e:
            logger.error(f"Erro ao obter segredo '{secret_name}' do Vault: {e}")
            return None
    
    def get_certificate(self, cert_name: str) -> Optional[bytes]:
        secret_value = self.get_secret(cert_name)
        if secret_value:
            if os.path.exists(secret_value):
                with open(secret_value, 'rb') as f:
                    return f.read()
            return secret_value.encode('utf-8')
        return None
    
    def is_available(self) -> bool:
        return self.client is not None and self.client.is_authenticated()


class AzureKeyVaultProvider(SecretProvider):
    """Provedor Azure Key Vault."""
    
    def __init__(self, vault_url: str = None):
        self.vault_url = vault_url or os.getenv('AZURE_KEY_VAULT_URL')
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.keyvault.secrets import SecretClient
                
                credential = DefaultAzureCredential()
                self._client = SecretClient(
                    vault_url=self.vault_url,
                    credential=credential
                )
                logger.info("Cliente Azure Key Vault inicializado")
            except ImportError:
                logger.warning("azure-identity ou azure-keyvault não instalados.")
                return None
            except Exception as e:
                logger.error(f"Erro ao inicializar Azure Key Vault: {e}")
                return None
        return self._client
    
    def get_secret(self, secret_name: str) -> Optional[str]:
        if not self.client:
            return None
        
        try:
            secret = self.client.get_secret(secret_name)
            return secret.value
        except Exception as e:
            logger.error(f"Erro ao obter segredo '{secret_name}' do Azure: {e}")
            return None
    
    def get_certificate(self, cert_name: str) -> Optional[bytes]:
        if not self.client:
            return None
        
        try:
            from azure.keyvault.certificates import CertificateClient
            from azure.identity import DefaultAzureCredential
            
            credential = DefaultAzureCredential()
            cert_client = CertificateClient(
                vault_url=self.vault_url,
                credential=credential
            )
            
            cert = cert_client.get_certificate(cert_name)
            return cert.cer
        except Exception as e:
            logger.error(f"Erro ao obter certificado '{cert_name}' do Azure: {e}")
            return None
    
    def is_available(self) -> bool:
        return self.client is not None


class SecretManager:
    """
    Gerenciador central de segredos com suporte multi-provedor.
    Implementa padrão Zero Trust para credenciais sensíveis.
    """
    
    def __init__(self):
        self.providers: list[SecretProvider] = []
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Inicializa provedores na ordem de prioridade."""
        
        # 1. AWS Secrets Manager
        if os.getenv('AWS_SECRET_MANAGER_ENABLED', 'false').lower() == 'true':
            aws_provider = AWSSecretsManagerProvider()
            if aws_provider.is_available():
                self.providers.append(aws_provider)
                logger.info("AWS Secrets Manager habilitado")
        
        # 2. HashiCorp Vault
        if os.getenv('VAULT_ENABLED', 'false').lower() == 'true':
            vault_provider = VaultProvider()
            if vault_provider.is_available():
                self.providers.append(vault_provider)
                logger.info("HashiCorp Vault habilitado")
        
        # 3. Azure Key Vault
        if os.getenv('AZURE_KEY_VAULT_ENABLED', 'false').lower() == 'true':
            azure_provider = AzureKeyVaultProvider()
            if azure_provider.is_available():
                self.providers.append(azure_provider)
                logger.info("Azure Key Vault habilitado")
        
        # 4. Fallback: Variáveis de Ambiente (sempre disponível)
        env_provider = EnvironmentSecretProvider()
        self.providers.append(env_provider)
        logger.info("Provedor de ambiente habilitado (fallback)")
    
    def get_secret(self, secret_name: str, provider_priority: list[str] = None) -> Optional[str]:
        """
        Obtém um segredo tentando os provedores em ordem de prioridade.
        
        Args:
            secret_name: Nome do segredo
            provider_priority: Lista opcional de provedores prioritários
            
        Returns:
            Valor do segredo ou None
        """
        for provider in self.providers:
            try:
                value = provider.get_secret(secret_name)
                if value is not None:
                    logger.debug(f"Segredo '{secret_name}' obtido via {provider.__class__.__name__}")
                    return value
            except Exception as e:
                logger.warning(f"Erro no provedor {provider.__class__.__name__}: {e}")
        
        logger.error(f"Segredo '{secret_name}' não encontrado em nenhum provedor")
        return None
    
    def get_certificate(self, cert_name: str) -> Optional[bytes]:
        """
        Obtém um certificado (arquivo .pfx ou .pem).
        
        Args:
            cert_name: Nome do certificado
            
        Returns:
            Conteúdo binário do certificado ou None
        """
        for provider in self.providers:
            try:
                cert_data = provider.get_certificate(cert_name)
                if cert_data is not None:
                    logger.debug(f"Certificado '{cert_name}' obtido via {provider.__class__.__name__}")
                    return cert_data
            except Exception as e:
                logger.warning(f"Erro no provedor {provider.__class__.__name__}: {e}")
        
        logger.error(f"Certificado '{cert_name}' não encontrado")
        return None
    
    def get_credentials(self, service_name: str) -> Dict[str, Any]:
        """
        Obtém todas as credenciais de um serviço específico.
        
        Args:
            service_name: Nome do serviço (ex: 'esocial', 'database')
            
        Returns:
            Dicionário com todas as credenciais
        """
        credentials = {}
        
        # Padrões comuns de nomes de segredos
        patterns = [
            f"{service_name}_username",
            f"{service_name}_password",
            f"{service_name}_token",
            f"{service_name}_api_key",
            f"{service_name}_secret",
            f"{service_name}_cert",
        ]
        
        for pattern in patterns:
            value = self.get_secret(pattern)
            if value:
                key = pattern.replace(f"{service_name}_", "")
                credentials[key] = value
        
        return credentials
    
    def validate_certificate(self, cert_name: str, password: str = None) -> bool:
        """
        Valida se um certificado está disponível e é legível.
        
        Args:
            cert_name: Nome do certificado
            password: Senha do certificado (opcional)
            
        Returns:
            True se válido, False caso contrário
        """
        cert_data = self.get_certificate(cert_name)
        if not cert_data:
            return False
        
        # Validação básica do formato
        try:
            from cryptography.hazmat.primitives.serialization import pkcs12, pem
            from cryptography.hazmat.backends import default_backend
            
            # Tenta carregar como PKCS12 (.pfx)
            try:
                pkcs12.load_key_and_certificates(
                    cert_data,
                    password.encode() if password else None,
                    default_backend()
                )
                logger.info(f"Certificado '{cert_name}' validado como PKCS12")
                return True
            except Exception:
                pass
            
            # Tenta carregar como PEM
            try:
                pem.load_pem_private_key(cert_data, password.encode() if password else None)
                logger.info(f"Certificado '{cert_name}' validado como PEM")
                return True
            except Exception:
                pass
            
            logger.warning(f"Certificado '{cert_name}' não pôde ser parseado")
            return False
            
        except ImportError:
            logger.warning("cryptography não disponível para validação detalhada")
            return len(cert_data) > 0
    
    def get_active_provider(self) -> str:
        """Retorna o nome do provedor ativo principal."""
        for provider in self.providers:
            if provider.is_available():
                return provider.__class__.__name__
        return "None"


# Singleton global
_secret_manager: Optional[SecretManager] = None


def get_secret_manager() -> SecretManager:
    """Obtém a instância singleton do SecretManager."""
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager()
    return _secret_manager


# Funções utilitárias para uso direto
def get_secret(secret_name: str) -> Optional[str]:
    """Obtém um segredo usando o gerenciador global."""
    return get_secret_manager().get_secret(secret_name)


def get_certificate(cert_name: str) -> Optional[bytes]:
    """Obtém um certificado usando o gerenciador global."""
    return get_secret_manager().get_certificate(cert_name)


def get_esocial_cert() -> Optional[bytes]:
    """Obtém o certificado do eSocial."""
    return get_certificate("esocial_cert")


def get_esocial_cert_password() -> Optional[str]:
    """Obtém a senha do certificado do eSocial."""
    return get_secret("esocial_cert_password")
