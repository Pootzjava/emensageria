"""
Módulo de validação XML estrita contra XSD do eSocial.
Valida documentos XML gerados contra os schemas oficiais da versão 1.3.
"""

from typing import Optional, List, Dict, Tuple
from pathlib import Path
from lxml import etree
import logging

logger = logging.getLogger(__name__)


class EsocialXMLValidator:
    """
    Validador de XML do eSocial contra schemas XSD oficiais.
    Suporta validação de eventos individuais e lotes completos.
    """
    
    def __init__(self, version: str = "v_S_01_03_00", xsd_dir: Optional[str] = None):
        """
        Inicializa o validador com a versão e diretório dos XSDs.
        
        Args:
            version: Versão do layout do eSocial (padrão: v_S_01_03_00)
            xsd_dir: Diretório onde estão os arquivos XSD (opcional)
        """
        self.version = version
        if xsd_dir:
            self.xsd_dir = Path(xsd_dir)
        else:
            # Caminho padrão relativo ao projeto
            base_dir = Path(__file__).parent.parent.parent
            self.xsd_dir = base_dir / "xsd" / "esocial" / version
        
        # Cache de schemas compilados
        self._schema_cache: Dict[str, etree.XMLSchema] = {}
        
        # Mapeamento de tipo de evento para arquivo XSD
        self.event_xsd_mapping = {
            'evtInfoEmpregador': 'evtInfoEmpregador_v_S_01_03_00.xsd',
            'evtTabRubrica': 'evtTabRubrica_v_S_01_03_00.xsd',
            'evtTabLotacao': 'evtTabLotacao_v_S_01_03_00.xsd',
            'evtTabProcesso': 'evtTabProcesso_v_S_01_03_00.xsd',
            'evtAdmissao': 'evtAdmissao_v_S_01_03_00.xsd',
            'evtAltContratual': 'evtAltContratual_v_S_01_03_00.xsd',
            'evtDeslig': 'evtDeslig_v_S_01_03_00.xsd',
            'evtReintegr': 'evtReintegr_v_S_01_03_00.xsd',
            'evtTSVInicio': 'evtTSVInicio_v_S_01_03_00.xsd',
            'evtTSVAltContr': 'evtTSVAltContr_v_S_01_03_00.xsd',
            'evtTSVTermino': 'evtTSVTermino_v_S_01_03_00.xsd',
            'evtPgtos': 'evtPgtos_v_S_01_03_00.xsd',
            'evtRemun': 'evtRemun_v_S_01_03_00.xsd',
            'evtComProd': 'evtComProd_v_S_01_03_00.xsd',
            'evtContrib': 'evtContrib_v_S_01_03_00.xsd',
            'evtBeneficio': 'evtBeneficio_v_S_01_03_00.xsd',
            'evtFechaEvPer': 'evtFechaEvPer_v_S_01_03_00.xsd',
            'evtReabreEvPer': 'evtReabreEvPer_v_S_01_03_00.xsd',
            'evtInfoComplPer': 'evtInfoComplPer_v_S_01_03_00.xsd',
            'evtExclusao': 'evtExclusao_v_S_01_03_00.xsd',
            'evtRetornoTrab': 'evtRetornoTrab_v_S_01_03_00.xsd',
            'evtLicense': 'evtLicense_v_S_01_03_00.xsd',
            'evtFechamento400': 'evtFechamento400_v_S_01_03_00.xsd',
        }
    
    def _load_schema(self, xsd_filename: str) -> Optional[etree.XMLSchema]:
        """
        Carrega e compila um schema XSD, usando cache se disponível.
        
        Args:
            xsd_filename: Nome do arquivo XSD
            
        Returns:
            Schema compilado ou None se falhar
        """
        if xsd_filename in self._schema_cache:
            return self._schema_cache[xsd_filename]
        
        xsd_path = self.xsd_dir / xsd_filename
        
        if not xsd_path.exists():
            logger.error(f"Arquivo XSD não encontrado: {xsd_path}")
            return None
        
        try:
            with open(xsd_path, 'rb') as f:
                schema_root = etree.XML(f.read())
            
            # Cria documento para resolver includes/imports
            schema_doc = etree.ElementTree(schema_root)
            
            # Define base directory para resolução de imports relativos
            parser = etree.XMLParser(
                resolve_entities=True,
                no_network=False,
                huge_tree=True
            )
            
            schema = etree.XMLSchema(schema_doc)
            self._schema_cache[xsd_filename] = schema
            logger.debug(f"Schema carregado com sucesso: {xsd_filename}")
            return schema
            
        except etree.XMLSchemaError as e:
            logger.error(f"Erro ao compilar schema {xsd_filename}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao carregar schema {xsd_filename}: {str(e)}")
            return None
    
    def validate_event(self, xml_content: str, event_type: Optional[str] = None) -> Dict:
        """
        Valida um evento XML individual contra o schema correspondente.
        
        Args:
            xml_content: Conteúdo XML do evento como string
            event_type: Tipo do evento (ex: 'evtInfoEmpregador'). 
                       Se None, tenta detectar automaticamente.
            
        Returns:
            Dicionário com resultado da validação:
            {
                'valid': bool,
                'errors': list,
                'warnings': list,
                'event_type': str,
                'schema_used': str
            }
        """
        result = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'event_type': event_type or 'desconhecido',
            'schema_used': None
        }
        
        # Parse do XML
        try:
            xml_doc = etree.fromstring(xml_content.encode('utf-8'))
        except etree.XMLSyntaxError as e:
            result['errors'].append({
                'type': 'syntax',
                'message': f'XML mal formado: {str(e)}',
                'line': e.position[0] if hasattr(e, 'position') else None
            })
            return result
        
        # Detecta tipo do evento se não fornecido
        if not event_type:
            event_type = xml_doc.tag.split('}')[-1] if '}' in xml_doc.tag else xml_doc.tag
            result['event_type'] = event_type
        
        # Remove prefixo evt se presente para busca no mapeamento
        event_key = event_type
        if event_type.startswith('evt'):
            event_key = event_type
        
        # Busca schema correspondente
        xsd_filename = self.event_xsd_mapping.get(event_key)
        
        if not xsd_filename:
            # Tenta buscar por nome genérico
            xsd_filename = f'{event_type}_{self.version}.xsd'
        
        schema = self._load_schema(xsd_filename)
        
        if not schema:
            result['errors'].append({
                'type': 'configuration',
                'message': f'Schema XSD não encontrado para o evento {event_type}'
            })
            return result
        
        result['schema_used'] = xsd_filename
        
        # Validação
        try:
            is_valid = schema.validate(xml_doc)
            
            if is_valid:
                result['valid'] = True
                result['warnings'].append('XML válido contra o schema XSD.')
            else:
                # Coleta erros de validação
                for error in schema.error_log:
                    result['errors'].append({
                        'type': 'schema',
                        'message': error.message,
                        'line': error.line,
                        'column': error.column,
                        'level': error.level_name
                    })
                    
        except Exception as e:
            result['errors'].append({
                'type': 'validation',
                'message': f'Erro durante validação: {str(e)}'
            })
        
        return result
    
    def validate_batch(self, xml_content: str) -> Dict:
        """
        Valida um lote completo de eventos.
        
        Args:
            xml_content: Conteúdo XML do lote
            
        Returns:
            Dicionário com resultado da validação do lote
        """
        result = {
            'valid': False,
            'lote_errors': [],
            'event_results': [],
            'summary': {
                'total_events': 0,
                'valid_events': 0,
                'invalid_events': 0
            }
        }
        
        # Primeiro valida estrutura do lote
        lote_schema = self._load_schema(f'envioLoteEventos_{self.version}.xsd')
        
        if not lote_schema:
            result['lote_errors'].append({
                'type': 'configuration',
                'message': 'Schema do lote não encontrado'
            })
            return result
        
        try:
            xml_doc = etree.fromstring(xml_content.encode('utf-8'))
        except etree.XMLSyntaxError as e:
            result['lote_errors'].append({
                'type': 'syntax',
                'message': f'XML do lote mal formado: {str(e)}'
            })
            return result
        
        # Valida estrutura do lote
        if not lote_schema.validate(xml_doc):
            for error in lote_schema.error_log:
                result['lote_errors'].append({
                    'type': 'schema',
                    'message': error.message,
                    'line': error.line,
                    'column': error.column
                })
            # Mesmo com erros no lote, continua para validar eventos individuais
        
        # Extrai e valida cada evento
        ns = {'ns': f'http://www.esocial.gov.br/schema/lote/eventos/{self.version}'}
        events = xml_doc.xpath('//ns:Evento', namespaces=ns)
        
        result['summary']['total_events'] = len(events)
        
        for i, event_elem in enumerate(events, 1):
            event_xml = etree.tostring(event_elem, encoding='unicode', pretty_print=True)
            event_result = self.validate_event(event_xml)
            
            result['event_results'].append(event_result)
            
            if event_result['valid']:
                result['summary']['valid_events'] += 1
            else:
                result['summary']['invalid_events'] += 1
        
        # Lote é válido apenas se estrutura e todos os eventos forem válidos
        result['valid'] = (
            len(result['lote_errors']) == 0 and 
            result['summary']['invalid_events'] == 0
        )
        
        return result
    
    def validate_file(self, file_path: str, is_batch: bool = False) -> Dict:
        """
        Valida um arquivo XML do disco.
        
        Args:
            file_path: Caminho para o arquivo XML
            is_batch: Se True, trata como lote; se False, como evento único
            
        Returns:
            Resultado da validação (mesmo formato de validate_event ou validate_batch)
        """
        path = Path(file_path)
        
        if not path.exists():
            return {
                'valid': False,
                'errors': [{
                    'type': 'file',
                    'message': f'Arquivo não encontrado: {file_path}'
                }]
            }
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
        except Exception as e:
            return {
                'valid': False,
                'errors': [{
                    'type': 'file',
                    'message': f'Erro ao ler arquivo: {str(e)}'
                }]
            }
        
        if is_batch:
            return self.validate_batch(xml_content)
        else:
            return self.validate_event(xml_content)


# Funções utilitárias
def validate_xml(xml_content: str, version: str = "v_S_01_03_00") -> Dict:
    """
    Função rápida para validar um XML.
    Detecta automaticamente se é lote ou evento único.
    """
    validator = EsocialXMLValidator(version=version)
    
    # Tenta detectar se é lote ou evento
    try:
        root = etree.fromstring(xml_content.encode('utf-8'))
        root_tag = root.tag.split('}')[-1] if '}' in root.tag else root.tag
        
        if root_tag == 'eSocial':
            return validator.validate_batch(xml_content)
        else:
            return validator.validate_event(xml_content)
    except Exception as e:
        return {
            'valid': False,
            'errors': [{
                'type': 'parse',
                'message': f'Erro ao analisar XML: {str(e)}'
            }]
        }


def validate_file(file_path: str, version: str = "v_S_01_03_00") -> Dict:
    """Função rápida para validar um arquivo XML."""
    validator = EsocialXMLValidator(version=version)
    return validator.validate_file(file_path)
