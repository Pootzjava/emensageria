"""
Módulo de Persistência e Dead Letter Queue (DLQ).

Responsável por:
- Persistir o estado dos lotes em disco para recovery.
- Gerenciar a fila de eventos falhos (DLQ).
- Garantir que o estado seja atômico e consistente.
"""
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class PersistenceError(Exception):
    """Erro ao persistir ou recuperar dados."""
    pass


class BatchState:
    """Representa o estado de um lote de transmissão."""
    
    def __init__(self, batch_id: str, events: List[Dict[str, Any]], status: str = 'PENDING'):
        self.batch_id = batch_id
        self.events = events
        self.status = status  # PENDING, SENT, PROCESSING, SUCCESS, FAILED
        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()
        self.retry_count = 0
        self.last_error: Optional[str] = None
        self.response_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'batch_id': self.batch_id,
            'events': self.events,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'retry_count': self.retry_count,
            'last_error': self.last_error,
            'response_data': self.response_data
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BatchState':
        state = cls(
            batch_id=data['batch_id'],
            events=data['events'],
            status=data.get('status', 'PENDING')
        )
        state.created_at = data.get('created_at', datetime.utcnow().isoformat())
        state.updated_at = data.get('updated_at', datetime.utcnow().isoformat())
        state.retry_count = data.get('retry_count', 0)
        state.last_error = data.get('last_error')
        state.response_data = data.get('response_data')
        return state


class PersistenceManager:
    """
    Gerencia a persistência de estados de lotes e a Dead Letter Queue.
    
    Usa arquivos JSON para simplicidade e portabilidade, mas com travas
    para garantir consistência em ambientes concorrentes.
    """
    
    def __init__(self, storage_path: str = "./esocial_storage"):
        self.storage_path = Path(storage_path)
        self.batches_path = self.storage_path / "batches"
        self.dlq_path = self.storage_path / "dlq"
        self._lock = threading.Lock()
        
        self._ensure_dirs()
        logger.info(f"PersistenceManager initialized at {self.storage_path}")

    def _ensure_dirs(self):
        """Cria diretórios se não existirem."""
        self.batches_path.mkdir(parents=True, exist_ok=True)
        self.dlq_path.mkdir(parents=True, exist_ok=True)

    def _get_batch_file(self, batch_id: str) -> Path:
        return self.batches_path / f"{batch_id}.json"

    def _get_dlq_file(self, event_id: str) -> Path:
        return self.dlq_path / f"{event_id}.json"

    def save_batch(self, state: BatchState) -> None:
        """Salva ou atualiza o estado de um lote."""
        state.updated_at = datetime.utcnow().isoformat()
        file_path = self._get_batch_file(state.batch_id)
        
        with self._lock:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)
                logger.debug(f"Batch {state.batch_id} state saved.")
            except Exception as e:
                logger.error(f"Failed to save batch {state.batch_id}: {e}")
                raise PersistenceError(f"Could not save batch state: {e}")

    def load_batch(self, batch_id: str) -> Optional[BatchState]:
        """Carrega o estado de um lote."""
        file_path = self._get_batch_file(batch_id)
        
        if not file_path.exists():
            return None
            
        with self._lock:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return BatchState.from_dict(data)
            except Exception as e:
                logger.error(f"Failed to load batch {batch_id}: {e}")
                return None

    def delete_batch(self, batch_id: str) -> bool:
        """Remove o arquivo de estado do lote (após sucesso confirmado)."""
        file_path = self._get_batch_file(batch_id)
        
        with self._lock:
            if file_path.exists():
                try:
                    file_path.unlink()
                    logger.debug(f"Batch {batch_id} state deleted.")
                    return True
                except Exception as e:
                    logger.error(f"Failed to delete batch {batch_id}: {e}")
                    return False
        return False

    def add_to_dlq(self, event: Dict[str, Any], error: str, context: Optional[Dict] = None) -> None:
        """Adiciona um evento falho à Dead Letter Queue."""
        event_id = event.get('id', f"unknown_{datetime.utcnow().timestamp()}")
        file_path = self._get_dlq_file(f"{event_id}_{int(time.time())}")
        
        dlq_entry = {
            'event': event,
            'error': error,
            'context': context or {},
            'failed_at': datetime.utcnow().isoformat(),
            'retry_count': 0
        }
        
        with self._lock:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(dlq_entry, f, indent=2, ensure_ascii=False)
                logger.warning(f"Event {event_id} added to DLQ: {error}")
            except Exception as e:
                logger.critical(f"Failed to add event to DLQ: {e}")
                # Se não conseguimos salvar na DLQ, logamos o evento em crash
                logger.critical(f"LOST EVENT DATA: {event}")

    def get_dlq_events(self) -> List[Dict[str, Any]]:
        """Retorna todos os eventos na DLQ."""
        events = []
        with self._lock:
            for file_path in self.dlq_path.glob("*.json"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        events.append(json.load(f))
                except Exception as e:
                    logger.error(f"Error reading DLQ file {file_path}: {e}")
        return events

    def remove_from_dlq(self, file_name: str) -> bool:
        """Remove um evento da DLQ após reprocessamento bem-sucedido."""
        file_path = self.dlq_path / file_name
        with self._lock:
            if file_path.exists():
                try:
                    file_path.unlink()
                    return True
                except Exception as e:
                    logger.error(f"Failed to remove from DLQ {file_name}: {e}")
                    return False
        return False

    def list_pending_batches(self) -> List[BatchState]:
        """Lista todos os lotes que não foram finalizados com sucesso."""
        batches = []
        with self._lock:
            for file_path in self.batches_path.glob("*.json"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        state = BatchState.from_dict(data)
                        if state.status not in ['SUCCESS']:
                            batches.append(state)
                except Exception as e:
                    logger.error(f"Error reading batch file {file_path}: {e}")
        return batches
