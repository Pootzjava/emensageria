"""
Testes de Conformidade e Validação do eSocial v1.3

Este módulo contém a suíte de testes de conformidade que valida
o sistema contra cenários reais e mutantes.
"""

from .compliance_tests import ComplianceTestCase, ComplianceTestRunner, XMLMutant

__all__ = ['ComplianceTestCase', 'ComplianceTestRunner', 'XMLMutant']
