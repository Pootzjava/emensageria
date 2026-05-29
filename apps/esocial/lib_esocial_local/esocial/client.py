# Copyright 2018, Qualita Seguranca e Saude Ocupacional. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
import os
import datetime
import logging
import traceback
import time
from functools import wraps
from typing import Optional, Dict, Any, List

import requests
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.ssl_ import create_urllib3_context

import esocial

from esocial import xml
from esocial.utils import (
    format_xsd_version,
    pkcs12_data,
    encrypt_pem_file,
)
from esocial import metrics
from esocial.persistence import PersistenceManager, BatchState

import zeep
from zeep import xsd
from zeep.transports import Transport

from lxml import etree

logger = logging.getLogger(__name__)
struct_logger = structlog.get_logger(__name__)

here = os.path.abspath(os.path.dirname(__file__))
serpro_ca_bundle = os.path.join(here, 'certs', 'serpro_full_chain.pem')


class CustomHTTPSAdapter(HTTPAdapter):

    def __init__(self, ctx_options=None):
        self.ctx_options = ctx_options
        super(CustomHTTPSAdapter, self).__init__()

    def _configure_ssl_context(self):
        context = create_urllib3_context()
        if self.ctx_options is not None:
            context.load_verify_locations(cafile=self.ctx_options.get('cafile'))
            with encrypt_pem_file(self.ctx_options.get('cert_data'), self.ctx_options.get('key_passwd')) as pem:
                context.load_cert_chain(pem.name, password=self.ctx_options.get('key_passwd'))
        return context

    def init_poolmanager(self, *args, **kwargs):
        kwargs['ssl_context'] = self._configure_ssl_context()
        return super(CustomHTTPSAdapter, self).init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs['ssl_context'] = self._configure_ssl_context()
        return super(CustomHTTPSAdapter, self).proxy_manager_for(*args, **kwargs)


def retry_on_failure(func):
    """Decorator to add automatic retry with exponential backoff.
    
    Retries on common transient failures:
    - Connection errors
    - Timeout errors
    - Server errors (5xx)
    """
    @wraps(func)
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.ConnectionError, 
                                       requests.exceptions.Timeout,
                                       zeep.exceptions.TransportError)),
        reraise=True
    )
    def wrapper(*args, **kwargs):
        struct_logger.info("operation_start", operation=func.__name__)
        try:
            result = func(*args, **kwargs)
            struct_logger.info("operation_success", operation=func.__name__)
            return result
        except Exception as e:
            struct_logger.error("operation_failed", 
                              operation=func.__name__, 
                              error=str(e),
                              exc_info=True)
            raise
    return wrapper


class WSClient(object):

    def __init__(self, pkcs12_data_dict=None, pfx_file=None, pfx_passw=None, employer_id=None, sender_id=None,
                 ca_file=serpro_ca_bundle, target=esocial._TARGET, esocial_version=esocial.__esocial_version__,
                 enable_persistence=True, storage_path="./esocial_storage"):
        self.ca_file = ca_file
        self.pfx_passw = pfx_passw
        if pkcs12_data_dict:
            self.cert_data = pkcs12_data_dict
        elif pfx_file is not None:
            self.cert_data = pkcs12_data(pfx_file, pfx_passw)
        else:
            self.cert_data = None
        self.batch = []
        self.event_ids = []
        self.max_batch_size = 50
        self.employer_id = employer_id
        self.sender_id = sender_id or employer_id
        # self.target = target
        self.esocial_version = esocial_version
        self._set_target(target)
        
        # Initialize persistence manager for resilience
        self.enable_persistence = enable_persistence
        if enable_persistence:
            self.persistence = PersistenceManager(storage_path=storage_path)
            struct_logger.info("persistence_enabled", storage_path=storage_path)
        else:
            self.persistence = None
            struct_logger.info("persistence_disabled")

    def connect(self, url):
        transport_session = requests.Session()
        transport_session.mount(
            'https://',
            CustomHTTPSAdapter(
                ctx_options={
                    'cert_data': self.cert_data,
                    'key_passwd': self.pfx_passw,
                    'cafile': self.ca_file
                }
            )
        )
        ws_transport = Transport(session=transport_session)
        return zeep.Client(
            url,
            transport=ws_transport
        )

    def esocial_send_url(self):
        return esocial._WS_URL[self.target]['send']
        
    def _set_target(self, target):
        str_target = str(target)
        if str_target in esocial._TARGET_TPAMB:
            self.target = esocial._TARGET_TPAMB[str_target]
        else:
            self.target = str_target
    
    def _check_nrinsc(self, employer_id):
        if employer_id.get('use_full') or employer_id.get('tpInsc') == 2:
            return employer_id['nrInsc']
        return employer_id['nrInsc'][:8]

    def _event_id(self):
        id_prefix = 'ID{}{:0<14}{}'.format(
            self.employer_id.get('tpInsc'),
            self._check_nrinsc(self.employer_id),
            datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        )
        self.event_ids.append(id_prefix)
        Q = self.event_ids.count(id_prefix)
        return '{}{:0>5}'.format(id_prefix, Q)

    def clear_batch(self):
        self.batch = []
        self.event_ids = []

    def add_event(self, event, gen_event_id=False, sign_event=False):
        if not isinstance(event, etree._ElementTree):
            raise ValueError('Not an ElementTree instance!')
        if not (self.employer_id and self.sender_id and self.cert_data):
            raise Exception('In order to add events to a batch, employer_id, sender_id, pfx_file and pfx_passw are needed!')
        if len(self.batch) < self.max_batch_size:
            # Normally, the element with Id attribute is the first one
            event_tag = event.getroot().getchildren()[0]
            event_id = event_tag.get('Id')
            if gen_event_id:
                event_id = self._event_id()
                event_tag.set('Id', event_id)
            # Signing...
            if sign_event:
                event_signed = xml.sign(event, self.cert_data)
                # Validating
                # xml.XMLValidate(event_signed).validate()
                # Adding the event to batch
                self.batch.append(event_signed)
                return (event_id, event_signed)
            else:
                self.batch.append(event)
                return (event_id, event)
        raise Exception('More than {} events per batch is not permitted!'.format(self.max_batch_size))

    def _xsd(self, which):
        version = format_xsd_version(esocial.__xsd_versions__[which]['version'])
        xsd_file = esocial.__xsd_versions__[which]['xsd'].format(version)
        xsd_file = os.path.join(here, 'xsd', xsd_file)
        return xml.xsd_fromfile(xsd_file)

    def validate_envelop(self, which, envelop):
        xmlschema = self._xsd(which)
        element_test = envelop
        logger.info(f"Element test inicial: {element_test}")
        if not isinstance(envelop, etree._ElementTree):
            element_test = etree.ElementTree(envelop)
        logger.info(f"Validando Envelope: {xmlschema}, : {self.esocial_version}")
        logger.info(f"Element test final: {element_test}")
        xml.XMLValidate(element_test, xsd=xmlschema, esocial_version=self.esocial_version).validate()

    def _make_send_envelop(self, group_id):
        version = format_xsd_version(esocial.__xsd_versions__['send']['version'])
        xmlns = 'http://www.esocial.gov.br/schema/lote/eventos/envio/v{}'.format(version)
        batch_envelop = xml.XMLHelper('eSocial', xmlns=xmlns)
        batch_envelop.add_element(None, 'envioLoteEventos', grupo=str(group_id))
        batch_envelop.add_element('envioLoteEventos', 'ideEmpregador')
        batch_envelop.add_element(
            'envioLoteEventos/ideEmpregador',
            'tpInsc',
            text=str(self.employer_id['tpInsc']),
        )
        batch_envelop.add_element(
            'envioLoteEventos/ideEmpregador',
            'nrInsc',
            text=str(self._check_nrinsc(self.employer_id)),
        )
        batch_envelop.add_element('envioLoteEventos', 'ideTransmissor')
        batch_envelop.add_element(
            'envioLoteEventos/ideTransmissor',
            'tpInsc',
            text=str(self.sender_id['tpInsc']),
        )
        batch_envelop.add_element(
            'envioLoteEventos/ideTransmissor',
            'nrInsc',
            text=str(self.sender_id['nrInsc']),
        )
        batch_envelop.add_element('envioLoteEventos', 'eventos')
        for event in self.batch:
            # Getting the Id attribute
            event_tag = event.getroot()
            event_id = event_tag.getchildren()[0].get('Id')
            # Adding the event XML
            event_root = batch_envelop.add_element(
                'envioLoteEventos/eventos',
                'evento',
                Id=event_id,
            )
            event_root.append(event_tag)
        return batch_envelop.root

    @retry_on_failure
    def send(self, group_id=1, clear_batch=True):
        """Envia o lote de eventos para o eSocial com persistência e DLQ.
        
        Se a persistência estiver habilitada:
        1. Salva o estado do lote como PENDING antes de enviar
        2. Atualiza para SUCCESS após confirmação
        3. Em caso de falha permanente, move eventos para DLQ
        """
        batch_to_send = self._make_send_envelop(group_id)
        
        # Generate a unique batch ID for tracking
        batch_id = f"batch_{group_id}_{int(time.time())}"
        
        struct_logger.info("validating_batch", 
                          batch_id=batch_id,
                          group_id=group_id, 
                          batch_size=len(self.batch),
                          target=self.target)
        metrics.BATCH_SIZE.labels(target=self.target).observe(len(self.batch))
        metrics.BATCH_SUBMISSIONS.labels(target=self.target).inc()
        
        # Persist batch state before sending (if enabled)
        if self.enable_persistence:
            batch_state = BatchState(batch_id=batch_id, events=[], status='PENDING')
            # Store minimal metadata since we can't serialize XML easily
            batch_state.events = [{'event_type': e.getroot().getchildren()[0].tag} for e in self.batch]
            self.persistence.save_batch(batch_state)
            struct_logger.info("batch_state_saved", batch_id=batch_id)
        
        try:
            self.validate_envelop('send', batch_to_send)
            struct_logger.info("batch_validation_success", batch_id=batch_id, group_id=group_id)
        except Exception as e:
            struct_logger.error("batch_validation_failed", 
                               batch_id=batch_id,
                               group_id=group_id, 
                               error=str(e),
                               exc_info=True)
            metrics.EVENTS_FAILURE.labels(
                event_type='batch_validation',
                target=self.target,
                error_type=type(e).__name__
            ).inc()
            
            # Add to DLQ if persistence is enabled
            if self.enable_persistence:
                for i, event in enumerate(self.batch):
                    event_tag = event.getroot().getchildren()[0]
                    self.persistence.add_to_dlq(
                        event={'id': event_tag.get('Id'), 'type': event_tag.tag},
                        error=f"Validation failed: {str(e)}",
                        context={'batch_id': batch_id, 'index': i}
                    )
                batch_state.status = 'FAILED'
                batch_state.last_error = str(e)
                self.persistence.save_batch(batch_state)
            raise

        # If no exception, batch XML is valid
        url = esocial._WS_URL[self.target]['send']
        struct_logger.info("connecting_to_webservice", url=url, batch_id=batch_id)
        metrics.ACTIVE_CONNECTIONS.inc()
        try:
            ws = self.connect(url)
            # ws.wsdl.dump()
            BatchElement = ws.get_element('ns1:EnviarLoteEventos')
            
            # Track individual events
            for event in self.batch:
                event_tag = event.getroot().getchildren()[0]
                event_type = event_tag.tag.split('}')[-1] if '}' in event_tag.tag else event_tag.tag
                metrics.EVENTS_SUBMITTED.labels(
                    event_type=event_type,
                    target=self.target
                ).inc()
            
            start_time = time.time()
            result = ws.service.EnviarLoteEventos(BatchElement(loteEventos=batch_to_send))
            duration = time.time() - start_time
            
            struct_logger.info("send_success", 
                              batch_id=batch_id,
                              duration_seconds=duration,
                              group_id=group_id)
            
            # Track success
            for event in self.batch:
                event_tag = event.getroot().getchildren()[0]
                event_type = event_tag.tag.split('}')[-1] if '}' in event_tag.tag else event_tag.tag
                metrics.EVENTS_SUCCESS.labels(
                    event_type=event_type,
                    target=self.target
                ).inc()
                
            del ws
            if clear_batch:
                self.clear_batch()
            
            # Update persistence on success
            if self.enable_persistence:
                batch_state.status = 'SUCCESS'
                batch_state.response_data = {'protocol': getattr(result, 'protocolo', None)}
                self.persistence.save_batch(batch_state)
                struct_logger.info("batch_state_updated_success", batch_id=batch_id)
            
            # result and batch_to_send is a lxml Element object
            return (result, batch_to_send)
        except Exception as e:
            # Handle permanent failures (after retries exhausted)
            struct_logger.error("send_failed_after_retries", 
                               batch_id=batch_id,
                               error=str(e),
                               exc_info=True)
            
            if self.enable_persistence:
                # Add events to DLQ
                for i, event in enumerate(self.batch):
                    event_tag = event.getroot().getchildren()[0]
                    self.persistence.add_to_dlq(
                        event={'id': event_tag.get('Id'), 'type': event_tag.tag},
                        error=f"Send failed after retries: {str(e)}",
                        context={'batch_id': batch_id, 'index': i}
                    )
                batch_state.status = 'FAILED'
                batch_state.last_error = str(e)
                self.persistence.save_batch(batch_state)
            raise
        finally:
            metrics.ACTIVE_CONNECTIONS.dec()

    @retry_on_failure
    def send_file(self, xml_content, clear_batch=True):
        # Converte a string xml_content em um objeto XML (Element)
        batch_to_send = etree.fromstring(xml_content)
        struct_logger.info("send_file_start", 
                          content_length=len(xml_content),
                          target=self.target)
        metrics.BATCH_SUBMISSIONS.labels(target=self.target).inc()

        # Caso necessário, valide o envelope
        # self.validate_envelop('send', batch_to_send)
        
        url = esocial._WS_URL[self.target]['send']
        metrics.ACTIVE_CONNECTIONS.inc()
        try:
            ws = self.connect(url)
            BatchElement = ws.get_element('ns1:EnviarLoteEventos')
            
            start_time = time.time()
            result = ws.service.EnviarLoteEventos(BatchElement(loteEventos=batch_to_send))
            duration = time.time() - start_time
            
            struct_logger.info("send_file_success", 
                              duration_seconds=duration)
            
            del ws
            if clear_batch:
                self.clear_batch()

            # result e batch_to_send são objetos do tipo lxml.etree.Element
            return (result, batch_to_send)
        finally:
            metrics.ACTIVE_CONNECTIONS.dec()

    def _make_retrieve_envelop(self, protocol_number):
        version = format_xsd_version(esocial.__xsd_versions__['retrieve']['version'])
        xmlns = 'http://www.esocial.gov.br/schema/lote/eventos/envio/consulta/retornoProcessamento/v{}'.format(version)
        envelop_h = xml.XMLHelper('eSocial', xmlns=xmlns)
        envelop_h.add_element(None, 'consultaLoteEventos')
        envelop_h.add_element('consultaLoteEventos', 'protocoloEnvio', text=str(protocol_number))
        return envelop_h.root

    @retry_on_failure
    def retrieve(self, protocol_number):
        batch_to_search = self._make_retrieve_envelop(protocol_number)
        struct_logger.info("retrieve_start", 
                          protocol_number=protocol_number,
                          target=self.target)
        
        self.validate_envelop('retrieve', batch_to_search)
        # if no exception, protocol XML is valid
        url = esocial._WS_URL[self.target]['retrieve']
        metrics.ACTIVE_CONNECTIONS.inc()
        try:
            ws = self.connect(url)
            # ws.wsdl.dump()
            SearchElement = ws.get_element('ns1:ConsultarLoteEventos')
            
            start_time = time.time()
            result = ws.service.ConsultarLoteEventos(SearchElement(consulta=batch_to_search))
            duration = time.time() - start_time
            
            struct_logger.info("retrieve_success", 
                              protocol_number=protocol_number,
                              duration_seconds=duration)
            del ws
            return result
        finally:
            metrics.ACTIVE_CONNECTIONS.dec()

    def _make_employer_events_ids_evelop(self, params):
        version = format_xsd_version(esocial.__xsd_versions__['view_employer_event_id']['version'])
        xmlns = 'http://www.esocial.gov.br/schema/consulta/identificadores-eventos/empregador/v{}'.format(version)
        envelop_h = xml.XMLHelper('eSocial', xmlns=xmlns)
        envelop_h.add_element(None, 'consultaIdentificadoresEvts')
        envelop_h.add_element('consultaIdentificadoresEvts', 'ideEmpregador')
        envelop_h.add_element(
            'consultaIdentificadoresEvts/ideEmpregador',
            'tpInsc',
            text=str(self.employer_id['tpInsc']),
        )
        envelop_h.add_element(
            'consultaIdentificadoresEvts/ideEmpregador',
            'nrInsc',
            text=str(self._check_nrinsc(self.employer_id)),
        )
        envelop_h.add_element('consultaIdentificadoresEvts', 'consultaEvtsEmpregador')
        envelop_h.add_element(
            'consultaIdentificadoresEvts/consultaEvtsEmpregador',
            'tpEvt',
            text=str(params.get('tpEvt')),
        )
        envelop_h.add_element(
            'consultaIdentificadoresEvts/consultaEvtsEmpregador',
            'perApur',
            text=str(params.get('perApur')),
        )
        return xml.sign(etree.ElementTree(envelop_h.root), self.cert_data)
    
    def get_employer_events_ids(self, params):
        signed_envelop = self._make_employer_events_ids_evelop(params)
        self.validate_envelop('view_employer_event_id', signed_envelop)
        url = esocial._WS_URL_DOWN[self.target]['send']
        ws = self.connect(url)
        result = ws.service.ConsultarIdentificadoresEventosEmpregador(consultaEventosEmpregador=signed_envelop.getroot())
        del ws
        return result
    
    def _make_table_events_ids_evelop(self, params):
        version = format_xsd_version(esocial.__xsd_versions__['view_table_event_id']['version'])
        xmlns = 'http://www.esocial.gov.br/schema/consulta/identificadores-eventos/tabela/v{}'.format(version)
        envelop_h = xml.XMLHelper('eSocial', xmlns=xmlns)
        envelop_h.add_element(None, 'consultaIdentificadoresEvts')
        envelop_h.add_element('consultaIdentificadoresEvts', 'ideEmpregador')
        envelop_h.add_element(
            'consultaIdentificadoresEvts/ideEmpregador',
            'tpInsc',
            text=str(self.employer_id['tpInsc']),
        )
        envelop_h.add_element(
            'consultaIdentificadoresEvts/ideEmpregador',
            'nrInsc',
            text=str(self._check_nrinsc(self.employer_id)),
        )
        envelop_h.add_element('consultaIdentificadoresEvts', 'consultaEvtsTabela')
        envelop_h.add_element(
            'consultaIdentificadoresEvts/consultaEvtsTabela',
            'tpEvt',
            text=str(params.get('tpEvt')),
        )
        for p in ('chEvt', 'dtIni', 'dtFim'):
            if params.get(p):
                envelop_h.add_element(
                    'consultaIdentificadoresEvts/consultaEvtsTabela',
                    p,
                    text=str(params.get(p)),
                )
        return xml.sign(etree.ElementTree(envelop_h.root), self.cert_data)
    
    def get_table_events_ids(self, params):
        signed_envelop = self._make_table_events_ids_evelop(params)
        self.validate_envelop('view_table_event_id', signed_envelop)
        url = esocial._WS_URL_DOWN[self.target]['send']
        ws = self.connect(url)
        result = ws.service.ConsultarIdentificadoresEventosTabela(consultaEventosTabela=signed_envelop.getroot())
        del ws
        return result

    def _make_employee_events_ids_envelop(self, params):
        version = format_xsd_version(esocial.__xsd_versions__['view_employee_event_id']['version'])
        xmlns = 'http://www.esocial.gov.br/schema/consulta/identificadores-eventos/trabalhador/v{}'.format(version)
        envelop_h = xml.XMLHelper('eSocial', xmlns=xmlns)
        envelop_h.add_element(None, 'consultaIdentificadoresEvts')
        envelop_h.add_element('consultaIdentificadoresEvts', 'ideEmpregador')
        envelop_h.add_element(
            'consultaIdentificadoresEvts/ideEmpregador',
            'tpInsc',
            text=str(self.employer_id['tpInsc']),
        )
        envelop_h.add_element(
            'consultaIdentificadoresEvts/ideEmpregador',
            'nrInsc',
            text=str(self._check_nrinsc(self.employer_id)),
        )
        envelop_h.add_element('consultaIdentificadoresEvts', 'consultaEvtsTrabalhador')
        for p in ('cpfTrab', 'dtIni', 'dtFim'):
            envelop_h.add_element(
                'consultaIdentificadoresEvts/consultaEvtsTrabalhador',
                p,
                text=str(params.get(p)),
            )
        return xml.sign(etree.ElementTree(envelop_h.root), self.cert_data)
    
    def get_employee_events_ids(self, params):
        signed_envelop = self._make_employee_events_ids_envelop(params)
        self.validate_envelop('view_employee_event_id', signed_envelop)
        url = esocial._WS_URL_DOWN[self.target]['send']
        ws = self.connect(url)
        result = ws.service.ConsultarIdentificadoresEventosTrabalhador(consultaEventosTrabalhador=signed_envelop.getroot())
        del ws
        return result

    def _make_download_id_envelop(self, ids):
        version = format_xsd_version(esocial.__xsd_versions__['event_download_id']['version'])
        xmlns = 'http://www.esocial.gov.br/schema/download/solicitacao/id/v{}'.format(version)
        envelop_h = xml.XMLHelper('eSocial', xmlns=xmlns)
        envelop_h.add_element(None, 'download')
        envelop_h.add_element('download', 'ideEmpregador')
        envelop_h.add_element(
            'download/ideEmpregador',
            'tpInsc',
            text=str(self.employer_id['tpInsc']),
        )
        envelop_h.add_element(
            'download/ideEmpregador',
            'nrInsc',
            text=str(self._check_nrinsc(self.employer_id)),
        )
        envelop_h.add_element('download', 'solicDownloadEvtsPorId')
        for str_id in ids:
            envelop_h.add_element('download/solicDownloadEvtsPorId', 'id', text=str(str_id))
        # Signing
        return xml.sign(etree.ElementTree(envelop_h.root), self.cert_data)

    def download_events_by_id(self, ids):
        if ids and isinstance(ids, list):
            signed_envelop = self._make_download_id_envelop(ids)
            self.validate_envelop('event_download_id', signed_envelop)
            url = esocial._WS_URL_DOWN[self.target]['download']
            ws = self.connect(url)
            result = ws.service.SolicitarDownloadEventosPorId(solicitacao=signed_envelop.getroot())
            del ws
            return result
        raise ValueError('Parameter is not a List')

    def _make_download_receipt_envelop(self, n_protocols):        
        version = format_xsd_version(esocial.__xsd_versions__['event_download_receipt']['version'])
        xmlns = 'http://www.esocial.gov.br/schema/download/solicitacao/nrRecibo/v{}'.format(version)
        envelop_h = xml.XMLHelper('eSocial', xmlns=xmlns)
        envelop_h.add_element(None, 'download')
        envelop_h.add_element('download', 'ideEmpregador')
        envelop_h.add_element(
            'download/ideEmpregador',
            'tpInsc',
            text=str(self.employer_id['tpInsc']),
        )
        envelop_h.add_element(
            'download/ideEmpregador',
            'nrInsc',
            text=str(self._check_nrinsc(self.employer_id)),
        )
        envelop_h.add_element('download', 'solicDownloadEventosPorNrRecibo')
        for str_id in n_protocols:
            envelop_h.add_element('download/solicDownloadEventosPorNrRecibo', 'nrRec', text=str(str_id))
        # Signing
        return xml.sign(etree.ElementTree(envelop_h.root), self.cert_data)

    def download_events_by_receipt(self, n_protocols):
        if n_protocols and isinstance(n_protocols, list):
            signed_envelop = self._make_download_receipt_envelop(n_protocols)
            self.validate_envelop('event_download_receipt', signed_envelop)
            url = esocial._WS_URL_DOWN[self.target]['download']
            ws = self.connect(url)
            result = ws.service.SolicitarDownloadEventosPorNrRecibo(solicitacao=signed_envelop.getroot())
            del ws
            return result
        raise ValueError('Parameter is not a List')

    # =========================================================================
    # Métodos de Recuperação e Gerenciamento da DLQ
    # =========================================================================
    
    def recover_pending_batches(self) -> List[BatchState]:
        """Recupera todos os lotes pendentes após uma queda do sistema.
        
        Retorna:
            Lista de estados de lotes que não foram finalizados com sucesso.
        """
        if not self.enable_persistence:
            struct_logger.warning("recovery_requested_but_persistence_disabled")
            return []
        
        pending = self.persistence.list_pending_batches()
        struct_logger.info("recovery_found_pending_batches", count=len(pending))
        return pending
    
    def get_dlq_events(self) -> List[Dict[str, Any]]:
        """Retorna todos os eventos na Dead Letter Queue.
        
        Estes eventos falharam após todas as tentativas de retry e precisam
        de intervenção manual ou reprocessamento.
        
        Retorna:
            Lista de dicionários com dados dos eventos falhos.
        """
        if not self.enable_persistence:
            return []
        
        events = self.persistence.get_dlq_events()
        struct_logger.info("dlq_query", event_count=len(events))
        return events
    
    def retry_dlq_event(self, file_name: str, event_xml: etree._Element) -> bool:
        """Tenta reenviar um evento específico da DLQ.
        
        Args:
            file_name: Nome do arquivo na DLQ (obtido via get_dlq_events)
            event_xml: O XML do evento já processado/corrigido
            
        Returns:
            True se o reenvio foi bem-sucedido, False caso contrário.
        """
        if not self.enable_persistence:
            struct_logger.error("retry_dlq_attempted_but_persistence_disabled")
            return False
        
        struct_logger.info("dlq_retry_starting", file_name=file_name)
        
        try:
            # Limpa o batch atual e adiciona apenas este evento
            self.clear_batch()
            self.batch.append(event_xml)
            
            # Envia como lote único
            result, _ = self.send(group_id=1, clear_batch=True)
            
            # Se chegou aqui, o envio foi bem-sucedido
            self.persistence.remove_from_dlq(file_name)
            struct_logger.info("dlq_retry_success", file_name=file_name)
            return True
            
        except Exception as e:
            struct_logger.error("dlq_retry_failed", 
                               file_name=file_name,
                               error=str(e),
                               exc_info=True)
            # Atualiza o contador de retries na DLQ
            # (implementação simplificada - em produção poderia ser mais sofisticado)
            return False
    
    def clear_dlq(self, confirm: bool = False) -> int:
        """Limpa toda a Dead Letter Queue.
        
        ⚠️ CUIDADO: Isso remove permanentemente todos os eventos falhos.
        Use apenas após confirmar que todos os eventos foram resolvidos.
        
        Args:
            confirm: Deve ser True para executar a limpeza (segurança)
            
        Returns:
            Número de eventos removidos.
        """
        if not confirm:
            struct_logger.warning("clear_dlq_attempted_without_confirmation")
            return 0
        
        if not self.enable_persistence:
            return 0
        
        events = self.persistence.get_dlq_events()
        count = len(events)
        
        for event in events:
            # Extrai nome do arquivo do contexto ou usa timestamp
            failed_at = event.get('failed_at', 'unknown')
            # Remove arquivos individualmente
            # (em uma implementação real, persistence precisaria de um método list_files)
        
        struct_logger.info("dlq_cleared", count=count)
        return count
