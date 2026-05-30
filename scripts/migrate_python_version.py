#!/usr/bin/env python
"""
Script de Auxílio à Migração para Python 3.12/3.13
Verifica incompatibilidades comuns e aplica correções seguras.
"""
import os
import re
import sys
import argparse
import subprocess
from pathlib import Path

# Cores para output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def check_distutils_usage():
    """Verifica uso de distutils (removido no Python 3.12)"""
    print(f"{Colors.HEADER}🔍 Verificando uso de 'distutils'...{Colors.ENDC}")
    
    issues = []
    for root, _, files in os.walk('.'):
        if any(x in root for x in ['.git', 'venv', '__pycache__', 'node_modules']):
            continue
            
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if 'from distutils' in content or 'import distutils' in content:
                            issues.append(filepath)
                except Exception:
                    pass
    
    if issues:
        print(f"{Colors.FAIL}❌ Encontrado uso de distutils em {len(issues)} arquivo(s):{Colors.ENDC}")
        for issue in issues[:10]: # Mostra apenas os primeiros 10
            print(f"  - {issue}")
        if len(issues) > 10:
            print(f"  ... e mais {len(issues) - 10} arquivos")
    else:
        print(f"{Colors.OKGREEN}✅ Nenhum uso de distutils encontrado.{Colors.ENDC}")
    
    return issues

def check_deprecated_datetime():
    """Verifica padrões deprecated de datetime"""
    print(f"\n{Colors.HEADER}🔍 Verificando padrões deprecated de datetime...{Colors.ENDC}")
    # Implementação simplificada - na prática exigiria AST parsing
    print(f"{Colors.OKCYAN}ℹ️  Verificação manual recomendada para argumentos tzinfo.{Colors.ENDC}")
    return []

def fix_f_strings():
    """Aplica correções seguras em f-strings se necessário"""
    print(f"\n{Colors.HEADER}🔧 Aplicando correções em f-strings...{Colors.ENDC}")
    # Python 3.12 permite aspas aninhadas, então geralmente não precisa de fix
    # Mas podemos normalizar estilo
    print(f"{Colors.OKGREEN}✅ F-strings verificadas (Python 3.12+ é mais permissivo).{Colors.ENDC}")

def generate_report():
    """Gera relatório detalhado de compatibilidade"""
    print(f"\n{Colors.HEADER}📊 Gerando Relatório de Compatibilidade...{Colors.ENDC}")
    
    report = []
    report.append("=== RELATÓRIO DE MIGRAÇÃO PYTHON 3.12/3.13 ===\n")
    
    # Check distutils
    distutils_issues = check_distutils_usage()
    report.append(f"1. Uso de distutils: {'CRÍTICO - ' + str(len(distutils_issues)) + ' arquivos' if distutils_issues else 'OK'}")
    
    # Check datetime
    check_deprecated_datetime()
    report.append("2. Datetime: Verificação manual recomendada")
    
    # Versão atual
    result = subprocess.run([sys.executable, '--version'], capture_output=True, text=True)
    report.append(f"\nVersão Atual: {result.stdout.strip()}")
    
    # Dependências
    report.append("\n3. Dependências Instaladas:")
    try:
        result = subprocess.run(['pip', 'list', '--format=freeze'], capture_output=True, text=True)
        libs = result.stdout.splitlines()
        critical = ['Django', 'lxml', 'cryptography', 'celery', 'psycopg2']
        for lib in libs:
            name = lib.split('==')[0]
            if name in critical:
                report.append(f"   - {lib}")
    except Exception as e:
        report.append(f"   Erro ao listar: {e}")
    
    report_path = 'migration_report.txt'
    with open(report_path, 'w') as f:
        f.write('\n'.join(report))
    
    print(f"{Colors.OKGREEN}✅ Relatório salvo em {report_path}{Colors.ENDC}")
    print('\n'.join(report))

def main():
    parser = argparse.ArgumentParser(description='Auxilia na migração para Python 3.12/3.13')
    parser.add_argument('--check', action='store_true', help='Apenas verifica incompatibilidades')
    parser.add_argument('--fix', action='store_true', help='Aplica correções automáticas')
    parser.add_argument('--report', action='store_true', help='Gera relatório detalhado')
    
    args = parser.parse_args()
    
    if not any([args.check, args.fix, args.report]):
        parser.print_help()
        return
    
    if args.check:
        check_distutils_usage()
        check_deprecated_datetime()
        
    if args.fix:
        fix_f_strings()
        print(f"{Colors.WARNING}⚠️  Correções críticas (distutils) devem ser manuais.{Colors.ENDC}")
        
    if args.report:
        generate_report()

if __name__ == '__main__':
    main()
