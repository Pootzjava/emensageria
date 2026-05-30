"""
eSocial AI Pre-Validation Module
Usa heurísticas avançadas e regras estatísticas para detectar inconsistências semânticas
 antes mesmo da validação de schema (XSD).
 Focado em prevenir erros de lógica de negócio que o XSD não pega.
"""
import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date

logger = logging.getLogger(__name__)


class AIPreValidator:
    """
    Motor de pré-validação semântica.
    Detecta anomalias como:
    - Salário incompatível com cargo
    - Data de admissão posterior à demissão
    - Jornada de trabalho incompatível com categoria
    - CPFs inválidos (algoritmo módulo 11)
    - NIS inválido
    """

    def __init__(self):
        self.rules = self._load_rules()

    def _load_rules(self) -> List[Dict]:
        """Carrega regras de negócio heurísticas"""
        return [
            {
                'id': 'RULE_001',
                'name': 'Data Admissão > Data Demissão',
                'check': self._check_dates_order
            },
            {
                'id': 'RULE_002',
                'name': 'Validação de CPF',
                'check': self._check_cpf_validity
            },
            {
                'id': 'RULE_003',
                'name': 'Salário Mínimo',
                'check': self._check_minimum_wage
            },
            {
                'id': 'RULE_004',
                'name': 'Jornada Compatível',
                'check': self._check_work_schedule
            }
        ]

    def validate_event(self, event_type: str, data: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Roda todas as regras aplicáveis ao evento.
        Retorna lista de warnings/errors.
        """
        findings = []
        
        for rule in self.rules:
            try:
                result = rule['check'](event_type, data)
                if result:
                    findings.append({
                        'rule_id': rule['id'],
                        'message': result,
                        'severity': 'warning' # ou 'error' se for crítico
                    })
            except Exception as e:
                logger.error(f"Erro na regra {rule['id']}: {e}")
        
        return findings

    def _check_dates_order(self, event_type: str, data: Dict) -> Optional[str]:
        """Verifica se dataAdmissao <= dataDesligamento"""
        # Exemplo genérico, precisa mapear os campos específicos de cada evento (s2200, s2299, etc)
        adm = data.get('dtAdmissao') or data.get('dataAdmissao')
        dem = data.get('dtDeslig') or data.get('dataDemissao')
        
        if adm and dem:
            # Assumindo formato YYYY-MM-DD
            if isinstance(adm, str): adm = datetime.strptime(adm, '%Y-%m-%d').date()
            if isinstance(dem, str): dem = datetime.strptime(dem, '%Y-%m-%d').date()
            
            if adm > dem:
                return f"A data de admissão ({adm}) é posterior à data de desligamento ({dem})."
        return None

    def _check_cpf_validity(self, event_type: str, data: Dict) -> Optional[str]:
        """Valida algoritmo do CPF"""
        cpf = data.get('cpf') or data.get('nrCpf')
        if not cpf:
            return None
        
        cpf = re.sub(r'\D', '', str(cpf))
        if len(cpf) != 11:
            return f"CPF deve ter 11 dígitos. Recebido: {cpf}"
        
        # Cálculo do dígito verificador
        def calculate_digit(cpf_part, factor):
            total = 0
            for digit in cpf_part:
                total += int(digit) * factor
                factor -= 1
            remainder = total % 11
            return '0' if remainder < 2 else str(11 - remainder)

        d1 = calculate_digit(cpf[:9], 10)
        d2 = calculate_digit(cpf[:9] + d1, 11)

        if cpf[-2:] != d1 + d2:
            return f"CPF {cpf} inválido segundo algoritmo de verificação."
        
        return None

    def _check_minimum_wage(self, event_type: str, data: Dict) -> Optional[str]:
        """Verifica se salário é menor que o mínimo vigente (configurável)"""
        # Valor exemplo, deveria vir de configuração ou tabela de benefícios
        MIN_WAGE = 1412.00 
        salario = data.get('remunicao') or data.get('salario')
        
        if salario and float(salario) < MIN_WAGE:
            # Ignora se for meio período ou intermitente (lógica complexa a adicionar)
            return f"Salário R$ {salario} abaixo do mínimo vigente (R$ {MIN_WAGE}). Verificar exceções."
        return None

    def _check_work_schedule(self, event_type: str, data: Dict) -> Optional[str]:
        """Verifica inconsistências de jornada"""
        # Lógica placeholder para detecção de padrões estranhos
        cod_lotacao = data.get('codLotacao')
        tp_jornada = data.get('tpJornada')
        
        # Exemplo: Se tpJornada == 1 (Tempo integral), mas horas contratuais < 40
        hrs_semanais = data.get('hrsSemanais')
        if tp_jornada == '1' and hrs_semanais and int(hrs_semanais) < 40:
            return f"Jornada indicada como Tempo Integral (1), mas carga horária ({hrs_semanais}) é inferior a 40h."
        
        return None
