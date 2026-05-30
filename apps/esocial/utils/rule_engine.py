"""
eSocial Rule Engine - Motor de Regras de Negócio Dinâmico
Permite atualizar regras de validação sem necessidade de deploy.
Suporte a JSON Logic e Django Rules.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, date
from django.utils import timezone

logger = logging.getLogger(__name__)


class RuleOperator:
    """Operadores básicos para regras."""
    
    OPERATORS = {
        'eq': lambda a, b: a == b,
        'ne': lambda a, b: a != b,
        'gt': lambda a, b: a > b,
        'gte': lambda a, b: a >= b,
        'lt': lambda a, b: a < b,
        'lte': lambda a, b: a <= b,
        'in': lambda a, b: a in b if isinstance(b, (list, tuple)) else False,
        'not_in': lambda a, b: a not in b if isinstance(b, (list, tuple)) else True,
        'contains': lambda a, b: b in a if isinstance(a, str) else False,
        'startswith': lambda a, b: a.startswith(b) if isinstance(a, str) else False,
        'endswith': lambda a, b: a.endswith(b) if isinstance(a, str) else False,
        'regex': lambda a, b: __import__('re').match(b, a) is not None if isinstance(a, str) else False,
        'is_null': lambda a, b: a is None,
        'is_not_null': lambda a, b: a is not None,
        'is_empty': lambda a, b: a in (None, '', [], {}),
        'is_not_empty': lambda a, b: a not in (None, '', [], {}),
        'between': lambda a, b: b[0] <= a <= b[1] if isinstance(b, (list, tuple)) and len(b) == 2 else False,
        'length_eq': lambda a, b: len(a) == b if hasattr(a, '__len__') else False,
        'length_gt': lambda a, b: len(a) > b if hasattr(a, '__len__') else False,
        'length_lt': lambda a, b: len(a) < b if hasattr(a, '__len__') else False,
    }
    
    @classmethod
    def execute(cls, operator: str, value: Any, expected: Any) -> bool:
        """Executa um operador sobre um valor."""
        if operator not in cls.OPERATORS:
            logger.warning(f"Operador desconhecido: {operator}")
            return False
        
        try:
            return cls.OPERATORS[operator](value, expected)
        except Exception as e:
            logger.error(f"Erro ao executar operador {operator}: {e}")
            return False


class RuleCondition:
    """Condição individual de uma regra."""
    
    def __init__(self, field: str, operator: str, value: Any):
        self.field = field
        self.operator = operator
        self.value = value
    
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Avalia a condição contra os dados fornecidos."""
        # Suporte a campos aninhados (ex: "trabalhador.cpf")
        value = self._get_nested_value(data, self.field)
        return RuleOperator.execute(self.operator, value, self.value)
    
    def _get_nested_value(self, data: Dict[str, Any], field: str) -> Any:
        """Obtém valor de campo aninhado."""
        keys = field.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
            
            if current is None:
                return None
        
        return current
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializa a condição para dicionário."""
        return {
            'field': self.field,
            'operator': self.operator,
            'value': self.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RuleCondition':
        """Cria condição a partir de dicionário."""
        return cls(
            field=data['field'],
            operator=data['operator'],
            value=data['value']
        )


class Rule:
    """Regra de negócio completa com múltiplas condições."""
    
    def __init__(self, 
                 rule_id: str,
                 name: str,
                 description: str,
                 event_type: str,
                 conditions: List[RuleCondition],
                 logic: str = 'AND',
                 error_message: str = None,
                 severity: str = 'ERROR',
                 enabled: bool = True,
                 priority: int = 100):
        """
        Inicializa uma regra.
        
        Args:
            rule_id: Identificador único da regra
            name: Nome descritivo da regra
            description: Descrição detalhada
            event_type: Tipo de evento eSocial (ex: S-1000, S-2200)
            conditions: Lista de condições da regra
            logic: 'AND' ou 'OR' para combinar condições
            error_message: Mensagem de erro quando a regra falha
            severity: Severidade ('ERROR', 'WARNING', 'INFO')
            enabled: Se a regra está ativa
            priority: Prioridade da regra (menor = mais prioritária)
        """
        self.rule_id = rule_id
        self.name = name
        self.description = description
        self.event_type = event_type
        self.conditions = conditions
        self.logic = logic.upper()
        self.error_message = error_message or f"Regra '{name}' não foi atendida"
        self.severity = severity.upper()
        self.enabled = enabled
        self.priority = priority
        self.created_at = timezone.now()
    
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """
        Avalia a regra contra os dados fornecidos.
        
        Returns:
            True se todas as condições forem satisfeitas (AND) ou 
            pelo menos uma (OR)
        """
        if not self.enabled:
            return True  # Regras desabilitadas sempre passam
        
        if not self.conditions:
            return True  # Sem condições = sempre passa
        
        results = [condition.evaluate(data) for condition in self.conditions]
        
        if self.logic == 'AND':
            return all(results)
        elif self.logic == 'OR':
            return any(results)
        else:
            logger.warning(f"Lógica desconhecida: {self.logic}, usando AND")
            return all(results)
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida os dados contra a regra e retorna resultado detalhado.
        
        Returns:
            Dicionário com:
            - passed: bool
            - message: str (se falhou)
            - severity: str
            - rule_id: str
        """
        passed = self.evaluate(data)
        
        result = {
            'passed': passed,
            'rule_id': self.rule_id,
            'rule_name': self.name,
            'severity': self.severity,
        }
        
        if not passed:
            result['message'] = self.error_message
            result['description'] = self.description
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializa a regra para dicionário."""
        return {
            'rule_id': self.rule_id,
            'name': self.name,
            'description': self.description,
            'event_type': self.event_type,
            'logic': self.logic,
            'error_message': self.error_message,
            'severity': self.severity,
            'enabled': self.enabled,
            'priority': self.priority,
            'conditions': [c.to_dict() for c in self.conditions],
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Rule':
        """Cria regra a partir de dicionário."""
        conditions = [
            RuleCondition.from_dict(c) 
            for c in data.get('conditions', [])
        ]
        
        return cls(
            rule_id=data['rule_id'],
            name=data['name'],
            description=data.get('description', ''),
            event_type=data['event_type'],
            conditions=conditions,
            logic=data.get('logic', 'AND'),
            error_message=data.get('error_message'),
            severity=data.get('severity', 'ERROR'),
            enabled=data.get('enabled', True),
            priority=data.get('priority', 100)
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Rule':
        """Cria regra a partir de JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def to_json(self) -> str:
        """Serializa a regra para JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class RuleEngine:
    """
    Motor de regras centralizado para validações do eSocial.
    Carrega regras do banco de dados, arquivos JSON ou configurações.
    """
    
    def __init__(self):
        self.rules: Dict[str, Rule] = {}
        self._load_default_rules()
    
    def _load_default_rules(self):
        """Carrega regras padrão do eSocial v1.3."""
        default_rules = self._get_default_rules_config()
        
        for rule_data in default_rules:
            try:
                rule = Rule.from_dict(rule_data)
                self.register_rule(rule)
            except Exception as e:
                logger.error(f"Erro ao carregar regra padrão {rule_data.get('rule_id')}: {e}")
    
    def _get_default_rules_config(self) -> List[Dict[str, Any]]:
        """Retorna configuração das regras padrão."""
        return [
            # Regra: CPF deve ter 11 dígitos
            {
                'rule_id': 'ESOCIAL_CPF_LENGTH',
                'name': 'CPF com tamanho válido',
                'description': 'O CPF deve conter exatamente 11 dígitos numéricos',
                'event_type': '*',  # Aplica-se a todos os eventos
                'logic': 'AND',
                'severity': 'ERROR',
                'error_message': 'CPF inválido: deve conter 11 dígitos',
                'conditions': [
                    {'field': 'cpf', 'operator': 'length_eq', 'value': 11},
                    {'field': 'cpf', 'operator': 'regex', 'value': r'^\\d{11}$'}
                ]
            },
            
            # Regra: CNPJ deve ter 14 dígitos
            {
                'rule_id': 'ESOCIAL_CNPJ_LENGTH',
                'name': 'CNPJ com tamanho válido',
                'description': 'O CNPJ deve conter exatamente 14 dígitos numéricos',
                'event_type': 'S-1000',
                'logic': 'AND',
                'severity': 'ERROR',
                'error_message': 'CNPJ inválido: deve conter 14 dígitos',
                'conditions': [
                    {'field': 'info_empregador.cnpj', 'operator': 'length_eq', 'value': 14},
                    {'field': 'info_empregador.cnpj', 'operator': 'regex', 'value': r'^\\d{14}$'}
                ]
            },
            
            # Regra: Data de nascimento não pode ser futura
            {
                'rule_id': 'ESOCIAL_DT_NASC_FUTURA',
                'name': 'Data de nascimento não futura',
                'description': 'A data de nascimento não pode ser posterior à data atual',
                'event_type': '*',
                'logic': 'AND',
                'severity': 'ERROR',
                'error_message': 'Data de nascimento inválida: não pode ser no futuro',
                'conditions': [
                    {'field': 'dt_nascimento', 'operator': 'lte', 'value': str(date.today())}
                ]
            },
            
            # Regra: Remuneração deve ser positiva
            {
                'rule_id': 'ESOCIAL_REMUNERACAO_POSITIVA',
                'name': 'Remuneração positiva',
                'description': 'O valor da remuneração deve ser maior que zero',
                'event_type': 'S-1200',
                'logic': 'AND',
                'severity': 'ERROR',
                'error_message': 'Remuneração inválida: deve ser maior que zero',
                'conditions': [
                    {'field': 'remuneracao.valor', 'operator': 'gt', 'value': 0}
                ]
            },
            
            # Regra: Matrícula obrigatória para empregados
            {
                'rule_id': 'ESOCIAL_MATRICULA_OBRIGATORIA',
                'name': 'Matrícula obrigatória',
                'description': 'Empregados devem ter matrícula cadastrada',
                'event_type': 'S-2200',
                'logic': 'AND',
                'severity': 'ERROR',
                'error_message': 'Matrícula é obrigatória para vínculo de empregado',
                'conditions': [
                    {'field': 'vinculo.matricula', 'operator': 'is_not_empty', 'value': None}
                ]
            },
            
            # Regra: CBO deve ter 6 dígitos
            {
                'rule_id': 'ESOCIAL_CBO_LENGTH',
                'name': 'CBO com tamanho válido',
                'description': 'O código CBO deve conter 6 dígitos',
                'event_type': '*',
                'logic': 'AND',
                'severity': 'WARNING',
                'error_message': 'CBO inválido: deve conter 6 dígitos',
                'conditions': [
                    {'field': 'cargo.cbo', 'operator': 'length_eq', 'value': 6}
                ]
            },
            
            # Regra: Salário mínimo vigente
            {
                'rule_id': 'ESOCIAL_SALARIO_MINIMO',
                'name': 'Salário acima do mínimo',
                'description': 'O salário não pode ser inferior ao salário mínimo vigente',
                'event_type': 'S-2200',
                'logic': 'AND',
                'severity': 'ERROR',
                'error_message': 'Salário abaixo do mínimo vigente',
                'conditions': [
                    {'field': 'remuneracao.salario', 'operator': 'gte', 'value': 1412.00}
                ]
            },
            
            # Regra: PIS/PASEP válido
            {
                'rule_id': 'ESOCIAL_PIS_VALIDO',
                'name': 'PIS/PASEP válido',
                'description': 'O número PIS/PASEP deve ter 11 dígitos',
                'event_type': '*',
                'logic': 'AND',
                'severity': 'ERROR',
                'error_message': 'PIS/PASEP inválido: deve conter 11 dígitos',
                'conditions': [
                    {'field': 'pis', 'operator': 'length_eq', 'value': 11}
                ]
            },
        ]
    
    def register_rule(self, rule: Rule):
        """Registra uma regra no motor."""
        self.rules[rule.rule_id] = rule
        logger.info(f"Regra registrada: {rule.rule_id} - {rule.name}")
    
    def unregister_rule(self, rule_id: str):
        """Remove uma regra do motor."""
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"Regra removida: {rule_id}")
    
    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Obtém uma regra pelo ID."""
        return self.rules.get(rule_id)
    
    def get_rules_for_event(self, event_type: str) -> List[Rule]:
        """
        Obtém todas as regras aplicáveis a um tipo de evento.
        
        Args:
            event_type: Tipo do evento (ex: S-1000, S-2200)
            
        Returns:
            Lista de regras ordenadas por prioridade
        """
        applicable_rules = []
        
        for rule in self.rules.values():
            # '*' significa que aplica-se a todos os eventos
            if rule.enabled and (rule.event_type == '*' or rule.event_type == event_type):
                applicable_rules.append(rule)
        
        # Ordena por prioridade (menor primeiro)
        return sorted(applicable_rules, key=lambda r: r.priority)
    
    def validate(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida dados contra todas as regras aplicáveis.
        
        Args:
            event_type: Tipo do evento
            data: Dados a serem validados
            
        Returns:
            Dicionário com:
            - valid: bool (True se todas passaram)
            - errors: list (erros encontrados)
            - warnings: list (avisos encontrados)
            - rules_evaluated: int (quantidade de regras avaliadas)
        """
        rules = self.get_rules_for_event(event_type)
        
        errors = []
        warnings = []
        
        for rule in rules:
            result = rule.validate(data)
            
            if not result['passed']:
                if result['severity'] == 'ERROR':
                    errors.append(result)
                elif result['severity'] == 'WARNING':
                    warnings.append(result)
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'rules_evaluated': len(rules),
            'event_type': event_type
        }
    
    def load_rules_from_json_file(self, file_path: str):
        """Carrega regras de um arquivo JSON."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                rules_data = json.load(f)
            
            if isinstance(rules_data, list):
                for rule_data in rules_data:
                    rule = Rule.from_dict(rule_data)
                    self.register_rule(rule)
            elif isinstance(rules_data, dict):
                rule = Rule.from_dict(rules_data)
                self.register_rule(rule)
            
            logger.info(f"Regras carregadas de {file_path}")
            
        except Exception as e:
            logger.error(f"Erro ao carregar regras de {file_path}: {e}")
            raise
    
    def load_rules_from_database(self):
        """
        Carrega regras do banco de dados Django.
        Requer modelo Rule configurado.
        """
        try:
            from apps.esocial.models import BusinessRule
            
            rules_qs = BusinessRule.objects.filter(enabled=True)
            
            for rule_obj in rules_qs:
                try:
                    rule = Rule.from_dict(rule_obj.to_dict())
                    self.register_rule(rule)
                except Exception as e:
                    logger.error(f"Erro ao carregar regra do BD {rule_obj.rule_id}: {e}")
            
            logger.info(f"{rules_qs.count()} regras carregadas do banco de dados")
            
        except ImportError:
            logger.warning("Modelo BusinessRule não encontrado")
        except Exception as e:
            logger.error(f"Erro ao carregar regras do BD: {e}")
    
    def export_rules_to_json(self, file_path: str, event_type: str = None):
        """Exporta regras para arquivo JSON."""
        if event_type:
            rules = self.get_rules_for_event(event_type)
        else:
            rules = list(self.rules.values())
        
        rules_data = [rule.to_dict() for rule in rules]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(rules_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"{len(rules)} regras exportadas para {file_path}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas das regras registradas."""
        total = len(self.rules)
        enabled = sum(1 for r in self.rules.values() if r.enabled)
        disabled = total - enabled
        
        by_severity = {}
        by_event = {}
        
        for rule in self.rules.values():
            by_severity[rule.severity] = by_severity.get(rule.severity, 0) + 1
            by_event[rule.event_type] = by_event.get(rule.event_type, 0) + 1
        
        return {
            'total_rules': total,
            'enabled': enabled,
            'disabled': disabled,
            'by_severity': by_severity,
            'by_event_type': by_event
        }


# Singleton global
_rule_engine: Optional[RuleEngine] = None


def get_rule_engine() -> RuleEngine:
    """Obtém a instância singleton do RuleEngine."""
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = RuleEngine()
    return _rule_engine


# Funções utilitárias
def validate_event(event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Valida dados de um evento contra todas as regras."""
    return get_rule_engine().validate(event_type, data)


def register_rule_from_json(json_str: str):
    """Registra uma regra a partir de JSON string."""
    rule = Rule.from_json(json_str)
    get_rule_engine().register_rule(rule)
    return rule
