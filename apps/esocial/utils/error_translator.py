"""
Módulo de utilitários para tradução e tratamento de erros do eSocial.
Traduz códigos de erro técnicos em mensagens amigáveis para o usuário final.
"""

from typing import Dict, Optional, List
import re


class EsocialErrorTranslator:
    """
    Tradutor de erros do eSocial.
    Converte códigos de erro técnicos e mensagens do governo em linguagem acessível.
    """

    # Mapeamento de códigos de erro comuns do eSocial
    ERROR_CODES = {
        # Erros de Validação de Schema (XSD)
        "101": "Erro de schema XML: A estrutura do arquivo não segue o padrão oficial.",
        "102": "Erro de tipo de dado: Um campo contém um valor incompatível (ex: texto onde deveria ser número).",
        "103": "Campo obrigatório ausente: Uma informação exigida pelo eSocial não foi preenchida.",
        "104": "Tamanho de campo excedido: Um texto está maior que o limite permitido.",
        "105": "Formato de data inválido: Use o formato AAAA-MM-DD (ex: 2024-01-15).",
        "106": "Formato de hora inválido: Use o formato HH:MM:SS (ex: 14:30:00).",
        "107": "Valor numérico fora do intervalo: O número informado é muito grande ou muito pequeno.",
        "108": "Caracteres especiais não permitidos: Remova acentos, símbolos ou caracteres especiais do campo.",
        
        # Erros de Regras de Negócio
        "201": "Evento já enviado: Este evento já foi transmitido com sucesso anteriormente.",
        "202": "Evento extemporâneo: A data de envio está fora do prazo permitido.",
        "203": "Período de apuração não aberto: O mês/ano informado ainda não está disponível para envio.",
        "204": "Período de apuração já fechado: O mês/ano informado já foi encerrado.",
        "205": "Trabalhador não encontrado: Não há registro ativo para este CPF/NIS no sistema.",
        "206": "Vínculo empregatício inexistente: Não foi encontrado vínculo para os dados informados.",
        "207": "Empregador não habilitado: O CNPJ/CPF do empregador não está habilitado no eSocial.",
        "208": "Inconsistência de informações: Os dados enviados conflitam com informações já existentes.",
        "209": "Evento dependente não enviado: É necessário enviar outro evento antes deste.",
        "210": "Dados cadastrais desatualizados: As informações do trabalhador/empregador precisam ser atualizadas.",
        
        # Erros de Certificado Digital
        "301": "Certificado digital inválido: O certificado não foi reconhecido ou está corrompido.",
        "302": "Certificado digital expirado: A validade do certificado venceu. Renove-o.",
        "303": "Certificado digital revogado: O certificado foi cancelado pela autoridade certificadora.",
        "304": "Assinatura digital inválida: A assinatura do XML não corresponde ao certificado.",
        "305": "Cadeia de certificação incompleta: Falta um certificado intermediário na validação.",
        
        # Erros de Comunicação/Serviço
        "401": "Serviço indisponível: O eSocial está em manutenção. Tente novamente mais tarde.",
        "402": "Timeout na comunicação: A conexão demorou muito. Verifique sua internet e tente novamente.",
        "403": "Acesso negado: Credenciais de acesso inválidas ou insuficientes.",
        "404": "URL do serviço não encontrada: Verifique a configuração do ambiente (Produção/Produção Restrita).",
        "405": "Limite de requisições excedido: Aguarde alguns minutos antes de tentar novamente.",
        
        # Erros Específicos de Eventos
        "501": "Remuneração acima do teto: O valor informado ultrapassa o limite do INSS.",
        "502": "Salário abaixo do mínimo: O valor informado é inferior ao salário mínimo vigente.",
        "503": "Carga horária incompatível: A jornada de trabalho informada é inconsistente.",
        "504": "Data de admissão futura: A data de ingresso não pode ser posterior à data atual.",
        "505": "Data de desligamento anterior à admissão: Verifique as datas de início e fim do vínculo.",
        "506": "FGTS já pago: Existe registro de pagamento para este período.",
        "507": "Benefício já concedido: Já existe um benefício ativo para este trabalhador.",
    }

    # Palavras-chave para detecção automática em mensagens de erro
    KEYWORD_MAPPING = {
        "schema": "Erro de estrutura XML: O arquivo não segue o formato oficial do eSocial.",
        "xsd": "Erro de validação formal: O documento não atende às especificações técnicas.",
        "obrigatório": "Campo faltante: Preencha todas as informações marcadas como obrigatórias.",
        "inválido": "Dado incorreto: Verifique o formato ou valor do campo informado.",
        "expirado": "Validade vencida: O certificado ou prazo informado não é mais válido.",
        "assinatura": "Problema na segurança: A assinatura digital não pôde ser verificada.",
        "certificado": "Problema no certificado: Verifique se o certificado digital está instalado e válido.",
        "timeout": "Conexão lenta: A comunicação com o eSocial demorou além do esperado.",
        "indisponível": "Sistema ocupado: O eSocial está temporariamente fora do ar.",
        "cpf": "Documento pessoal: Verifique se o CPF está correto e sem dígitos repetidos.",
        "cnpj": "Documento da empresa: Verifique se o CNPJ está correto e ativo.",
        "nis": "Número social: Confirme se o NIS/PIS está correto.",
        "data": "Informação de tempo: Verifique se a data está no formato correto (AAAA-MM-DD).",
        "valor": "Informação numérica: Confira se o valor está dentro dos limites aceitáveis.",
        "vínculo": "Relação de trabalho: Não foi encontrado vínculo ativo para este trabalhador.",
        "período": "Intervalo de tempo: O mês/ano informado não está disponível para envio.",
        "extemporâneo": "Fora do prazo: Este evento deveria ter sido enviado em uma data anterior.",
        "já enviado": "Duplicidade: Este evento já foi transmitido com sucesso.",
        "inconsistente": "Contradição de dados: As informações enviadas conflitam com registros existentes.",
    }

    @classmethod
    def translate(cls, error_code: Optional[str] = None, error_message: str = "") -> str:
        """
        Traduz um erro do eSocial para linguagem amigável.
        
        Args:
            error_code: Código do erro (ex: "101", "205")
            error_message: Mensagem completa do erro
            
        Returns:
            Mensagem amigável explicando o erro e sugerindo ação
        """
        friendly_message = ""
        suggestions = []

        # Tenta encontrar por código exato
        if error_code and error_code in cls.ERROR_CODES:
            friendly_message = cls.ERROR_CODES[error_code]
        
        # Se não encontrou por código, tenta análise semântica da mensagem
        if not friendly_message and error_message:
            friendly_message = cls._analyze_message(error_message)
            suggestions = cls._generate_suggestions(error_message)
        
        # Se ainda não encontrou, retorna mensagem genérica
        if not friendly_message:
            friendly_message = "Ocorreu um erro na comunicação com o eSocial. Verifique os detalhes técnicos."
        
        # Adiciona sugestões se houver
        if suggestions:
            friendly_message += "\n\n💡 Sugestões:\n" + "\n".join(f"• {s}" for s in suggestions)
        
        return friendly_message

    @classmethod
    def _analyze_message(cls, message: str) -> str:
        """Analisa a mensagem de erro em busca de palavras-chave conhecidas."""
        message_lower = message.lower()
        
        # Busca por palavras-chave
        for keyword, translation in cls.KEYWORD_MAPPING.items():
            if keyword in message_lower:
                return translation
        
        # Tenta extrair código numérico da mensagem
        code_match = re.search(r'\b(\d{3})\b', message)
        if code_match:
            code = code_match.group(1)
            if code in cls.ERROR_CODES:
                return cls.ERROR_CODES[code]
        
        return ""

    @classmethod
    def _generate_suggestions(cls, message: str) -> List[str]:
        """Gera sugestões de ação baseadas na mensagem de erro."""
        suggestions = []
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["certificado", "assinatura", "expirado"]):
            suggestions.append("Verifique se o certificado digital está instalado corretamente.")
            suggestions.append("Confirme se o certificado não venceu (validade).")
            suggestions.append("Teste o certificado em outro sistema para garantir que funciona.")
        
        if any(word in message_lower for word in ["schema", "xsd", "xml", "estrutura"]):
            suggestions.append("Valide o XML gerado antes de enviar.")
            suggestions.append("Verifique se todos os campos obrigatórios estão preenchidos.")
            suggestions.append("Confirme se está usando a versão correta do layout (v1.3).")
        
        if any(word in message_lower for word in ["timeout", "indisponível", "conexão"]):
            suggestions.append("Verifique sua conexão com a internet.")
            suggestions.append("Aguarde alguns minutos e tente novamente.")
            suggestions.append("Consulte o status do eSocial no site oficial.")
        
        if any(word in message_lower for word in ["cpf", "nis", "trabalhador"]):
            suggestions.append("Confira se o CPF/NIS está digitado corretamente.")
            suggestions.append("Verifique se o trabalhador está cadastrado no sistema.")
        
        if any(word in message_lower for word in ["cnpj", "empregador"]):
            suggestions.append("Verifique se o CNPJ da empresa está ativo na Receita Federal.")
            suggestions.append("Confirme se a empresa está habilitada no eSocial.")
        
        if any(word in message_lower for word in ["data", "período", "prazo"]):
            suggestions.append("Verifique se a data está no formato AAAA-MM-DD.")
            suggestions.append("Confirme se o período de apuração está aberto.")
        
        if "extemporâneo" in message_lower:
            suggestions.append("Este evento precisa ser enviado através de procedimento específico para fora de prazo.")
            suggestions.append("Consulte o manual de orientação do eSocial para eventos extemporâneos.")
        
        if "já enviado" in message_lower or "duplicidade" in message_lower:
            suggestions.append("Consulte os eventos já enviados para este período.")
            suggestions.append("Se precisar corrigir, envie um evento de retificação.")
        
        return suggestions

    @classmethod
    def get_error_summary(cls, errors: List[Dict]) -> str:
        """
        Gera um resumo amigável de múltiplos erros.
        
        Args:
            errors: Lista de dicionários com 'code' e 'message' de cada erro
            
        Returns:
            Resumo consolidado em linguagem amigável
        """
        if not errors:
            return "Nenhum erro encontrado."
        
        summary = f"Foram encontrados {len(errors)} erro(s):\n\n"
        
        for i, error in enumerate(errors, 1):
            code = error.get('code', '')
            message = error.get('message', '')
            friendly = cls.translate(code, message)
            summary += f"{i}. {friendly}\n\n"
        
        return summary


# Funções utilitárias de uso rápido
def translate_error(code: Optional[str] = None, message: str = "") -> str:
    """Função rápida para traduzir um erro."""
    return EsocialErrorTranslator.translate(code, message)


def get_error_details(xml_response: str) -> Dict:
    """
    Extrai e traduz erros de uma resposta XML do eSocial.
    
    Args:
        xml_response: XML completo da resposta do eSocial
        
    Returns:
        Dicionário com erros traduzidos
    """
    from lxml import etree
    
    errors = []
    try:
        root = etree.fromstring(xml_response.encode('utf-8'))
        
        # Namespace do eSocial
        ns = {'ns': 'http://www.esocial.gov.br/schema/lote/eventos/v_S_01_03_00'}
        
        # Busca por elementos de erro
        for error_elem in root.xpath('//ns:erroIdeLote | //ns:erroRegistro | //ns:retornoProcessamento/ns:erro', namespaces=ns):
            code_elem = error_elem.find('.//ns:codigo', namespaces=ns)
            msg_elem = error_elem.find('.//ns:descricao', namespaces=ns)
            
            if code_elem is not None and msg_elem is not None:
                code = code_elem.text or ""
                message = msg_elem.text or ""
                friendly = EsocialErrorTranslator.translate(code, message)
                
                errors.append({
                    'code': code,
                    'original_message': message,
                    'friendly_message': friendly,
                    'xml_element': etree.tostring(error_elem, encoding='unicode')
                })
    except Exception:
        # Se falhar ao parsear, retorna erro genérico
        errors.append({
            'code': '999',
            'original_message': 'Não foi possível processar a resposta XML.',
            'friendly_message': 'Erro ao processar resposta do eSocial. Verifique o log técnico.',
            'xml_element': xml_response[:500]
        })
    
    return {
        'has_errors': len(errors) > 0,
        'error_count': len(errors),
        'errors': errors,
        'summary': EsocialErrorTranslator.get_error_summary(errors)
    }
