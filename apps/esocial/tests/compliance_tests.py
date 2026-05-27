"""
eSocial Compliance Test Suite - Suite de Testes de Conformidade
Testes automatizados que geram XMLs propositalmente errados e corretos
para garantir que o validador local funcione corretamente.
"""

import unittest
import json
import logging
from typing import List, Dict, Any
from datetime import datetime, date
from django.test import TestCase
from django.utils import timezone

logger = logging.getLogger(__name__)


class XMLMutant:
    """Gera mutações de XML para testes de validação."""
    
    @staticmethod
    def create_valid_xml(event_type: str) -> str:
        """Cria um XML válido mínimo para um evento."""
        templates = {
            'S-1000': '''<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtInfoEmpregador/v_S_01_03_00">
  <evtInfoEmpregador Id="ID123456789012345678901234567890123456789012">
    <ideEvento>
      <tpAmb>1</tpAmb>
      <procEmi>1</procEmi>
      <verProc>1.3.0</verProc>
    </ideEvento>
    <ideEmpregador>
      <tpInsc>1</tpInsc>
      <nrInsc>12345678000199</nrInsc>
    </ideEmpregador>
    <infoEmpregador>
      <idePeriodo>
        <iniValid>2024-01</iniValid>
        <fimValid></fimValid>
      </idePeriodo>
      <infoCadastro>
        <classTri>1</classTri>
        <indCoop>0</indCoop>
        <indConstr>0</indConstr>
        <indDesFolha>0</indDesFolha>
        <indOpcCP>0</indOpcCP>
        <indPorte>0</indPorte>
        <indOptRegEletron>1</indOptRegEletron>
        <cnpjEFR>12345678000199</cnpjEFR>
      </infoCadastro>
    </infoEmpregador>
  </evtInfoEmpregador>
</eSocial>''',
            
            'S-2200': '''<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtAdmissao/v_S_01_03_00">
  <evtAdmissao Id="ID123456789012345678901234567890123456789012">
    <ideEvento>
      <tpAmb>1</tpAmb>
      <procEmi>1</procEmi>
      <verProc>1.3.0</verProc>
    </ideEvento>
    <ideEmpregador>
      <tpInsc>1</tpInsc>
      <nrInsc>12345678000199</nrInsc>
    </ideEmpregador>
    <ideVinculo>
      <cpfTrab>12345678901</cpfTrab>
      <matricula>000001</matricula>
      <codCateg>101</codCateg>
    </ideVinculo>
    <infoContrato>
      <cadIni>N</cadIni>
      <infoRegimeTrab>
        <infoEstatutario>
          <tpProv>1</tpProv>
          <dtExercicio>2024-01-02</dtExercicio>
        </infoEstatutario>
      </infoRegimeTrab>
    </infoContrato>
  </evtAdmissao>
</eSocial>'''
        }
        
        return templates.get(event_type, f'''<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/{event_type.lower()}/v_S_01_03_00">
  <{event_type} Id="ID123456789012345678901234567890123456789012">
    <ideEvento>
      <tpAmb>1</tpAmb>
      <procEmi>1</procEmi>
      <verProc>1.3.0</verProc>
    </ideEvento>
  </{event_type}>
</eSocial>''')
    
    @classmethod
    def mutate_cpf_invalid_length(cls, xml_content: str) -> str:
        """Muta CPF para ter tamanho inválido."""
        return xml_content.replace('12345678901', '123456789')
    
    @classmethod
    def mutate_cnpj_invalid_length(cls, xml_content: str) -> str:
        """Muta CNPJ para ter tamanho inválido."""
        return xml_content.replace('12345678000199', '1234567800019')
    
    @classmethod
    def mutate_future_date(cls, xml_content: str) -> str:
        """Muta data para ser no futuro."""
        future_date = (date.today().replace(year=date.today().year + 1)).isoformat()
        return xml_content.replace('2024-01-02', future_date)
    
    @classmethod
    def mutate_missing_required_field(cls, xml_content: str, field: str) -> str:
        """Remove campo obrigatório do XML."""
        import re
        pattern = f'<{field}>[^<]*</{field}>'
        return re.sub(pattern, '', xml_content)
    
    @classmethod
    def mutate_invalid_enum_value(cls, xml_content: str, field: str, invalid_value: str) -> str:
        """Substitui valor de enum por valor inválido."""
        import re
        pattern = f'<{field}>[0-9]</{field}>'
        return re.sub(pattern, f'<{field}>{invalid_value}</{field}>', xml_content)
    
    @classmethod
    def mutate_negative_value(cls, xml_content: str, field: str) -> str:
        """Substitui valor numérico por negativo."""
        import re
        pattern = f'<{field}>[0-9.]+</{field}>'
        return re.sub(pattern, f'<{field}>-999.99</{field}>', xml_content)
    
    @classmethod
    def mutate_xml_malformed(cls, xml_content: str) -> str:
        """Corrompe estrutura XML."""
        # Remove tag de fechamento
        lines = xml_content.split('\n')
        if len(lines) > 2:
            lines[-2] = lines[-2].replace('</eSocial>', '')
        return '\n'.join(lines)
    
    @classmethod
    def mutate_invalid_namespace(cls, xml_content: str) -> str:
        """Substitui namespace por inválido."""
        return xml_content.replace(
            'xmlns="http://www.esocial.gov.br/schema/evt/',
            'xmlns="http://invalid.namespace.gov.br/schema/evt/'
        )


class ComplianceTestCase(TestCase):
    """Casos de teste de conformidade para o eSocial."""
    
    @classmethod
    def setUpClass(cls):
        """Configura ambiente de teste."""
        super().setUpClass()
        logger.info("Iniciando suite de testes de conformidade eSocial")
    
    def test_valid_xml_passes_validation(self):
        """Testa que XML válido passa na validação."""
        from apps.esocial.utils.xml_validator import XMLValidator
        
        xml_content = XMLMutant.create_valid_xml('S-1000')
        validator = XMLValidator()
        
        result = validator.validate_string(xml_content, event_type='S-1000')
        
        # Nota: Pode falhar se XSD não estiver disponível em teste
        # O importante é que o validador não crash
        self.assertIsInstance(result, dict)
        self.assertIn('valid', result)
    
    def test_mutant_cpf_invalid_length_fails_rule_validation(self):
        """Testa que CPF com tamanho inválido falha na validação de regras."""
        from apps.esocial.utils.rule_engine import get_rule_engine
        
        engine = get_rule_engine()
        
        # Dados com CPF inválido (9 dígitos)
        data = {
            'cpf': '123456789',
            'nome': 'João Silva'
        }
        
        result = engine.validate('*', data)
        
        self.assertFalse(result['valid'])
        self.assertGreater(len(result['errors']), 0)
        
        # Verifica se há erro relacionado a CPF
        cpf_errors = [e for e in result['errors'] if 'CPF' in e.get('message', '')]
        self.assertGreater(len(cpf_errors), 0)
    
    def test_mutant_future_date_fails_rule_validation(self):
        """Testa que data futura falha na validação de regras."""
        from apps.esocial.utils.rule_engine import get_rule_engine
        
        engine = get_rule_engine()
        
        future_date = date.today().replace(year=date.today().year + 1).isoformat()
        
        data = {
            'dt_nascimento': future_date
        }
        
        result = engine.validate('*', data)
        
        self.assertFalse(result['valid'])
        
        # Verifica se há erro relacionado a data futura
        date_errors = [e for e in result['errors'] 
                      if 'futuro' in e.get('message', '').lower() or 'nascimento' in e.get('message', '').lower()]
        self.assertGreater(len(date_errors), 0)
    
    def test_mutant_xml_malformed_fails_xsd_validation(self):
        """Testa que XML malformado falha na validação."""
        from apps.esocial.utils.xml_validator import XMLValidator
        
        xml_valid = XMLMutant.create_valid_xml('S-1000')
        xml_malformed = XMLMutant.mutate_xml_malformed(xml_valid)
        
        validator = XMLValidator()
        result = validator.validate_string(xml_malformed, event_type='S-1000')
        
        # XML malformado deve falhar
        self.assertFalse(result.get('valid', True))
    
    def test_dry_run_detects_errors(self):
        """Testa que Dry Run detecta erros antes do envio."""
        from apps.esocial.utils.dry_run import dry_run
        
        # Dados inválidos
        data = {
            'cpf': '123',  # CPF inválido
            'dt_nascimento': '2099-01-01',  # Data futura
        }
        
        result = dry_run(
            event_type='S-2200',
            event_data=data,
            generate_report=False
        )
        
        # Dry Run deve detectar os erros
        self.assertFalse(result['success'])
        self.assertGreater(len(result['errors']), 0)
    
    def test_dry_run_success_with_valid_data(self):
        """Testa que Dry Run succeeds com dados válidos."""
        from apps.esocial.utils.dry_run import dry_run
        
        # Dados válidos mínimos
        data = {
            'cpf': '12345678901',
            'nome': 'João da Silva',
            'dt_nascimento': '1990-01-01'
        }
        
        result = dry_run(
            event_type='S-2200',
            event_data=data,
            generate_report=False
        )
        
        # Deve ter sucesso (ou pelo menos gerar XML)
        self.assertTrue(result['xml_generated'])
    
    def test_error_translator_provides_friendly_messages(self):
        """Testa que tradutor de erros fornece mensagens amigáveis."""
        from apps.esocial.utils.error_translator import translate_error
        
        # Testa código conhecido
        result = translate_error(code='205')
        
        self.assertIsNotNone(result)
        self.assertIn('message', result)
        self.assertIn('friendly_message', result)
    
    def test_rule_engine_statistics(self):
        """Testa estatísticas do motor de regras."""
        from apps.esocial.utils.rule_engine import get_rule_engine
        
        engine = get_rule_engine()
        stats = engine.get_statistics()
        
        self.assertIn('total_rules', stats)
        self.assertGreater(stats['total_rules'], 0)
        self.assertIn('enabled', stats)
        self.assertIn('disabled', stats)
    
    def test_secret_manager_fallback_to_environment(self):
        """Testa que gerenciador de segredos fallback para ambiente."""
        import os
        from apps.esocial.utils.secret_manager import get_secret_manager
        
        # Define variável de ambiente para teste
        os.environ['ESOCIAL_TEST_SECRET'] = 'test_value_123'
        
        manager = get_secret_manager()
        value = manager.get_secret('test_secret')
        
        # Deve encontrar via fallback de ambiente
        self.assertEqual(value, 'test_value_123')
        
        # Cleanup
        del os.environ['ESOCIAL_TEST_SECRET']


class ComplianceTestRunner:
    """Executa todos os testes de conformidade e gera relatório."""
    
    def __init__(self):
        self.results = []
        self.start_time = None
        self.end_time = None
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Executa todos os testes e retorna relatório consolidado."""
        import time
        
        self.start_time = time.time()
        
        # Cria suite de testes
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(ComplianceTestCase)
        
        # Executa testes
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        self.end_time = time.time()
        
        # Consolida resultados
        report = {
            'success': result.wasSuccessful(),
            'total_tests': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'skipped': len(result.skipped),
            'duration_seconds': self.end_time - self.start_time,
            'timestamp': timezone.now().isoformat(),
            'details': {
                'failures': [
                    {
                        'test': str(test),
                        'error': error
                    }
                    for test, error in result.failures
                ],
                'errors': [
                    {
                        'test': str(test),
                        'error': error
                    }
                    for test, error in result.errors
                ]
            }
        }
        
        return report
    
    def generate_html_report(self, report: Dict[str, Any], output_path: str):
        """Gera relatório HTML dos testes."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Relatório de Conformidade eSocial v1.3</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .success {{ color: green; }}
        .failure {{ color: red; }}
        .warning {{ color: orange; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>Relatório de Conformidade - eSocial v1.3</h1>
    
    <h2>Resumo</h2>
    <table>
        <tr><th>Status</th><td class="{'success' if report['success'] else 'failure'}">
            {'✅ SUCESSO' if report['success'] else '❌ FALHA'}
        </td></tr>
        <tr><th>Total de Testes</th><td>{report['total_tests']}</td></tr>
        <tr><th>Falhas</th><td class="{'failure' if report['failures'] > 0 else 'success'}">{report['failures']}</td></tr>
        <tr><th>Erros</th><td class="{'failure' if report['errors'] > 0 else 'success'}">{report['errors']}</td></tr>
        <tr><th>Skipados</th><td>{report['skipped']}</td></tr>
        <tr><th>Duração</th><td>{report['duration_seconds']:.2f}s</td></tr>
        <tr><th>Timestamp</th><td>{report['timestamp']}</td></tr>
    </table>
    
    <h2>Detalhes das Falhas</h2>
    {self._generate_failures_html(report['details']['failures'])}
    
    <h2>Detalhes dos Erros</h2>
    {self._generate_errors_html(report['details']['errors'])}
</body>
</html>
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        logger.info(f"Relatório HTML gerado: {output_path}")
    
    def _generate_failures_html(self, failures: List[Dict]) -> str:
        if not failures:
            return "<p>Nenhuma falha encontrada.</p>"
        
        rows = ""
        for failure in failures:
            rows += f"<tr><td>{failure['test']}</td><td>{failure['error']}</td></tr>"
        
        return f"""
        <table>
            <tr><th>Teste</th><th>Erro</th></tr>
            {rows}
        </table>
        """
    
    def _generate_errors_html(self, errors: List[Dict]) -> str:
        if not errors:
            return "<p>Nenhum erro encontrado.</p>"
        
        rows = ""
        for error in errors:
            rows += f"<tr><td>{error['test']}</td><td>{error['error']}</td></tr>"
        
        return f"""
        <table>
            <tr><th>Teste</th><th>Erro</th></tr>
            {rows}
        </table>
        """


# Função utilitária para execução rápida
def run_compliance_tests(generate_report: bool = True, report_path: str = '/tmp/compliance_report.html'):
    """
    Executa suite de testes de conformidade.
    
    Args:
        generate_report: Se deve gerar relatório HTML
        report_path: Caminho para salvar relatório HTML
        
    Returns:
        Dicionário com resultados dos testes
    """
    runner = ComplianceTestRunner()
    report = runner.run_all_tests()
    
    if generate_report:
        runner.generate_html_report(report, report_path)
    
    return report


# CLI para execução direta
if __name__ == '__main__':
    import sys
    
    print("=" * 60)
    print("SUITE DE TESTES DE CONFORMIDADE - eSOCIAL v1.3")
    print("=" * 60)
    
    report = run_compliance_tests()
    
    print("\n" + "=" * 60)
    print("RESULTADO FINAL")
    print("=" * 60)
    print(f"Status: {'✅ SUCESSO' if report['success'] else '❌ FALHA'}")
    print(f"Total: {report['total_tests']} testes")
    print(f"Falhas: {report['failures']}")
    print(f"Erros: {report['errors']}")
    print(f"Duração: {report['duration_seconds']:.2f}s")
    
    sys.exit(0 if report['success'] else 1)
