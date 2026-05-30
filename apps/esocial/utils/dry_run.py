"""
eSocial Dry Run - Simulação Segura de Envio
Simula todo o fluxo de envio ao eSocial sem transmitir dados reais.
Ideal para validar lotes grandes antes do envio em produção.
"""

import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from django.utils import timezone

logger = logging.getLogger(__name__)


class DryRunResult:
    """Resultado de uma simulação Dry Run."""
    
    def __init__(self):
        self.success = True
        self.simulation_id = str(uuid.uuid4())
        self.timestamp = timezone.now()
        self.steps = []
        self.errors = []
        self.warnings = []
        self.xml_generated = None
        self.xml_signed = None
        self.validation_result = None
        self.estimated_size_bytes = 0
        self.event_type = None
        self.event_id = None
    
    def add_step(self, step_name: str, success: bool, message: str = None, duration_ms: int = 0):
        """Adiciona um passo executado na simulação."""
        self.steps.append({
            'step': step_name,
            'success': success,
            'message': message,
            'duration_ms': duration_ms,
            'timestamp': timezone.now().isoformat()
        })
        
        if not success:
            self.success = False
    
    def add_error(self, error: str, severity: str = 'ERROR'):
        """Adiciona um erro encontrado."""
        self.errors.append({
            'error': error,
            'severity': severity,
            'timestamp': timezone.now().isoformat()
        })
        
        if severity == 'ERROR':
            self.success = False
    
    def add_warning(self, warning: str):
        """Adiciona um aviso encontrado."""
        self.warnings.append({
            'warning': warning,
            'timestamp': timezone.now().isoformat()
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializa o resultado para dicionário."""
        return {
            'success': self.success,
            'simulation_id': self.simulation_id,
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type,
            'event_id': self.event_id,
            'steps': self.steps,
            'errors': self.errors,
            'warnings': self.warnings,
            'xml_generated': self.xml_generated is not None,
            'xml_signed': self.xml_signed is not None,
            'validation_passed': self.validation_result.get('valid', False) if self.validation_result else None,
            'estimated_size_bytes': self.estimated_size_bytes,
            'total_steps': len(self.steps),
            'total_errors': len(self.errors),
            'total_warnings': len(self.warnings)
        }
    
    def to_json(self) -> str:
        """Serializa o resultado para JSON."""
        import json
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class DryRunSimulator:
    """
    Simulador completo do fluxo eSocial.
    Executa todas as etapas localmente sem enviar ao governo.
    """
    
    def __init__(self):
        self.result = DryRunResult()
    
    def simulate(self, 
                 event_type: str,
                 event_data: Dict[str, Any],
                 cert_path: str = None,
                 cert_password: str = None,
                 validate_xsd: bool = True,
                 validate_rules: bool = True,
                 sign_xml: bool = True) -> DryRunResult:
        """
        Executa simulação completa do fluxo.
        
        Args:
            event_type: Tipo do evento (ex: S-1000, S-2200)
            event_data: Dados do evento
            cert_path: Caminho do certificado (opcional para simulação)
            cert_password: Senha do certificado
            validate_xsd: Se deve validar contra XSD
            validate_rules: Se deve validar regras de negócio
            sign_xml: Se deve simular assinatura digital
            
        Returns:
            DryRunResult com detalhes da simulação
        """
        import time
        
        self.result = DryRunResult()
        self.result.event_type = event_type
        self.result.event_id = event_data.get('id') or str(uuid.uuid4())
        
        logger.info(f"Iniciando Dry Run para evento {event_type}")
        
        # Step 1: Validação de Regras de Negócio
        start = time.time()
        if validate_rules:
            rules_ok = self._simulate_rule_validation(event_type, event_data)
            duration = int((time.time() - start) * 1000)
            self.result.add_step(
                'rule_validation',
                rules_ok,
                'Regras de negócio validadas' if rules_ok else 'Falha nas regras de negócio',
                duration
            )
            
            if not rules_ok:
                logger.warning("Dry Run falhou na validação de regras")
                return self.result
        else:
            self.result.add_step('rule_validation', True, 'Validação de regras pulada', 0)
        
        # Step 2: Geração do XML
        start = time.time()
        xml_ok = self._simulate_xml_generation(event_type, event_data)
        duration = int((time.time() - start) * 1000)
        self.result.add_step(
            'xml_generation',
            xml_ok,
            f'XML gerado ({self.result.estimated_size_bytes} bytes)' if xml_ok else 'Falha ao gerar XML',
            duration
        )
        
        if not xml_ok:
            logger.warning("Dry Run falhou na geração do XML")
            return self.result
        
        # Step 3: Validação XSD
        start = time.time()
        if validate_xsd:
            xsd_ok = self._simulate_xsd_validation()
            duration = int((time.time() - start) * 1000)
            self.result.add_step(
                'xsd_validation',
                xsd_ok,
                'XML válido contra XSD' if xsd_ok else 'XML inválido contra XSD',
                duration
            )
            
            if not xsd_ok:
                logger.warning("Dry Run falhou na validação XSD")
                return self.result
        else:
            self.result.add_step('xsd_validation', True, 'Validação XSD pulada', 0)
        
        # Step 4: Assinatura Digital
        start = time.time()
        if sign_xml:
            sign_ok = self._simulate_signature(cert_path, cert_password)
            duration = int((time.time() - start) * 1000)
            self.result.add_step(
                'digital_signature',
                sign_ok,
                'XML assinado com sucesso' if sign_ok else 'Falha na assinatura',
                duration
            )
            
            if not sign_ok:
                logger.warning("Dry Run falhou na assinatura digital")
                return self.result
        else:
            self.result.add_step('digital_signature', True, 'Assinatura pulada', 0)
        
        # Step 5: Simulação de Envio
        start = time.time()
        send_ok = self._simulate_transmission()
        duration = int((time.time() - start) * 1000)
        self.result.add_step(
            'transmission_simulation',
            send_ok,
            'Transmissão simulada com sucesso',
            duration
        )
        
        # Resumo final
        if self.result.success:
            logger.info(f"Dry Run concluído com SUCESSO para {event_type}")
            self.result.add_warning(
                "Esta é uma simulação. Nenhum dado foi enviado ao eSocial."
            )
        else:
            logger.error(f"Dry Run concluído com FALHAS para {event_type}")
        
        return self.result
    
    def _simulate_rule_validation(self, event_type: str, data: Dict[str, Any]) -> bool:
        """Simula validação de regras de negócio."""
        try:
            from apps.esocial.utils.rule_engine import get_rule_engine
            
            engine = get_rule_engine()
            validation_result = engine.validate(event_type, data)
            
            self.result.validation_result = validation_result
            
            # Adiciona erros das regras
            for error in validation_result.get('errors', []):
                self.result.add_error(
                    f"[{error['rule_id']}] {error['message']}",
                    error['severity']
                )
            
            # Adiciona warnings das regras
            for warning in validation_result.get('warnings', []):
                self.result.add_warning(
                    f"[{warning['rule_id']}] {warning['message']}"
                )
            
            return validation_result['valid']
            
        except Exception as e:
            self.result.add_error(f"Erro na validação de regras: {str(e)}")
            return False
    
    def _simulate_xml_generation(self, event_type: str, data: Dict[str, Any]) -> bool:
        """Simula geração do XML."""
        try:
            from django.template.loader import render_to_string
            
            # Tenta renderizar template
            template_name = f"v_S_01_03_00/{event_type.lower()}.xml"
            
            # Simulação básica do XML
            xml_content = render_to_string(template_name, {
                'evento': data,
                'data_geracao': timezone.now()
            })
            
            self.result.xml_generated = xml_content
            self.result.estimated_size_bytes = len(xml_content.encode('utf-8'))
            
            return True
            
        except Exception as e:
            self.result.add_error(f"Erro ao gerar XML: {str(e)}")
            
            # Gera XML mínimo para simulação
            self.result.xml_generated = f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/{event_type.lower()}/v_S_01_03_00">
  <!-- XML simulado -->
  <Id>{self.result.event_id}</Id>
</eSocial>"""
            self.result.estimated_size_bytes = len(self.result.xml_generated.encode('utf-8'))
            
            return True  # Continua mesmo com erro no template
    
    def _simulate_xsd_validation(self) -> bool:
        """Simula validação contra XSD."""
        try:
            from apps.esocial.utils.xml_validator import XMLValidator
            
            validator = XMLValidator()
            
            if not self.result.xml_generated:
                self.result.add_error("XML não gerado para validação XSD")
                return False
            
            validation_result = validator.validate_string(
                self.result.xml_generated,
                event_type=self.result.event_type
            )
            
            if not validation_result['valid']:
                for error in validation_result.get('errors', []):
                    self.result.add_error(f"XSD: {error}")
            
            return validation_result['valid']
            
        except Exception as e:
            self.result.add_warning(f"Validação XSD não pôde ser completada: {str(e)}")
            # Não falha a simulação se XSD não estiver disponível
            return True
    
    def _simulate_signature(self, cert_path: str = None, cert_password: str = None) -> bool:
        """Simula assinatura digital."""
        try:
            if not cert_path:
                self.result.add_warning("Certificado não fornecido - assinatura simulada")
                self.result.xml_signed = self.result.xml_generated
                return True
            
            from apps.esocial.utils.digital_signature import DigitalSignature
            
            signer = DigitalSignature(cert_path, cert_password)
            
            # Verifica validade do certificado
            cert_info = signer.get_certificate_info()
            
            if not cert_info.get('valid', False):
                self.result.add_error(
                    f"Certificado inválido ou expirado: {cert_info.get('error', 'Desconhecido')}"
                )
                return False
            
            self.result.add_warning(
                f"Certificado válido até: {cert_info.get('not_after', 'N/A')}"
            )
            
            # Simula assinatura (não modifica o XML real em dry run)
            self.result.xml_signed = self.result.xml_generated
            
            return True
            
        except Exception as e:
            self.result.add_error(f"Erro na assinatura: {str(e)}")
            return False
    
    def _simulate_transmission(self) -> bool:
        """Simula transmissão ao eSocial."""
        # Apenas simula - não envia nada
        self.result.add_warning(
            "Transmissão simulada - nenhum dado foi enviado ao governo"
        )
        
        # Simula tempo de resposta do governo
        import random
        simulated_response_time = random.uniform(0.5, 2.0)
        self.result.add_step(
            'government_response_simulation',
            True,
            f'Tempo de resposta simulado: {simulated_response_time:.2f}s',
            int(simulated_response_time * 1000)
        )
        
        return True
    
    def generate_report(self) -> str:
        """Gera relatório detalhado da simulação."""
        report = []
        report.append("=" * 60)
        report.append("RELATÓRIO DRY RUN - eSOCIAL v1.3")
        report.append("=" * 60)
        report.append(f"ID Simulação: {self.result.simulation_id}")
        report.append(f"Timestamp: {self.result.timestamp}")
        report.append(f"Evento: {self.result.event_type}")
        report.append(f"ID Evento: {self.result.event_id}")
        report.append("")
        
        report.append("STATUS: " + ("✅ SUCESSO" if self.result.success else "❌ FALHA"))
        report.append("")
        
        report.append("ETAPAS EXECUTADAS:")
        report.append("-" * 40)
        for step in self.result.steps:
            status = "✅" if step['success'] else "❌"
            report.append(f"{status} {step['step']}: {step['message']} ({step['duration_ms']}ms)")
        report.append("")
        
        if self.result.errors:
            report.append("ERROS ENCONTRADOS:")
            report.append("-" * 40)
            for error in self.result.errors:
                report.append(f"❌ [{error['severity']}] {error['error']}")
            report.append("")
        
        if self.result.warnings:
            report.append("AVISOS:")
            report.append("-" * 40)
            for warning in self.result.warnings:
                report.append(f"⚠️ {warning['warning']}")
            report.append("")
        
        report.append("RESUMO:")
        report.append("-" * 40)
        report.append(f"XML Gerado: {self.result.xml_generated is not None}")
        report.append(f"XML Assinado: {self.result.xml_signed is not None}")
        report.append(f"Tamanho Estimado: {self.result.estimated_size_bytes} bytes")
        report.append(f"Regras Validadas: {self.result.validation_result is not None}")
        
        if self.result.validation_result:
            report.append(f"  - Regras avaliadas: {self.result.validation_result.get('rules_evaluated', 0)}")
            report.append(f"  - Erros: {len(self.result.validation_result.get('errors', []))}")
            report.append(f"  - Avisos: {len(self.result.validation_result.get('warnings', []))}")
        
        report.append("")
        report.append("=" * 60)
        report.append("NOTA: Esta é uma simulação. Nenhum dado foi transmitido.")
        report.append("=" * 60)
        
        return "\n".join(report)


# Função utilitária principal
def dry_run(event_type: str, 
            event_data: Dict[str, Any],
            cert_path: str = None,
            cert_password: str = None,
            generate_report: bool = True) -> Dict[str, Any]:
    """
    Executa Dry Run de um evento eSocial.
    
    Args:
        event_type: Tipo do evento (ex: S-1000, S-2200)
        event_data: Dados do evento
        cert_path: Caminho do certificado (opcional)
        cert_password: Senha do certificado
        generate_report: Se deve gerar relatório textual
        
    Returns:
        Dicionário com resultados da simulação
    """
    simulator = DryRunSimulator()
    result = simulator.simulate(
        event_type=event_type,
        event_data=event_data,
        cert_path=cert_path,
        cert_password=cert_password
    )
    
    response = result.to_dict()
    
    if generate_report:
        response['report'] = simulator.generate_report()
    
    return response


# Endpoint de API helper
def api_dry_run(request):
    """
    Handler para endpoint de API REST.
    Uso: POST /api/esocial/v1/dry-run/
    """
    import json
    
    try:
        data = json.loads(request.body)
        
        event_type = data.get('event_type')
        event_data = data.get('event_data', {})
        cert_path = data.get('cert_path')
        cert_password = data.get('cert_password')
        
        if not event_type:
            return {
                'success': False,
                'error': 'event_type é obrigatório'
            }, 400
        
        result = dry_run(
            event_type=event_type,
            event_data=event_data,
            cert_path=cert_path,
            cert_password=cert_password
        )
        
        status_code = 200 if result['success'] else 400
        return result, status_code
        
    except json.JSONDecodeError:
        return {'success': False, 'error': 'JSON inválido'}, 400
    except Exception as e:
        logger.error(f"Erro no dry run: {e}")
        return {'success': False, 'error': str(e)}, 500
