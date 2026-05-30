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
"""Metrics module for monitoring eSocial operations.

This module provides Prometheus metrics for tracking:
- Event submissions
- Success/failure rates
- Response times
- Batch processing
"""
import time
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from functools import wraps

# Metrics definitions
EVENTS_SUBMITTED = Counter(
    'esocial_events_submitted_total',
    'Total number of events submitted to eSocial',
    ['event_type', 'target']
)

EVENTS_SUCCESS = Counter(
    'esocial_events_success_total',
    'Total number of successfully processed events',
    ['event_type', 'target']
)

EVENTS_FAILURE = Counter(
    'esocial_events_failure_total',
    'Total number of failed events',
    ['event_type', 'target', 'error_type']
)

BATCH_SUBMISSIONS = Counter(
    'esocial_batch_submissions_total',
    'Total number of batch submissions',
    ['target']
)

REQUEST_DURATION = Histogram(
    'esocial_request_duration_seconds',
    'Time spent on eSocial requests',
    ['operation', 'target'],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, float('inf'))
)

BATCH_SIZE = Histogram(
    'esocial_batch_size',
    'Size of event batches',
    ['target'],
    buckets=(1, 5, 10, 20, 30, 40, 50, 100)
)

ACTIVE_CONNECTIONS = Gauge(
    'esocial_active_connections',
    'Number of active connections to eSocial'
)


def track_operation(operation_name, target='unknown'):
    """Decorator to track operation duration and success/failure.
    
    Args:
        operation_name: Name of the operation being tracked
        target: Target environment (production, tests, etc.)
    
    Returns:
        Decorated function with metrics tracking
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                REQUEST_DURATION.labels(
                    operation=operation_name,
                    target=target
                ).observe(duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                REQUEST_DURATION.labels(
                    operation=operation_name,
                    target=target
                ).observe(duration)
                EVENTS_FAILURE.labels(
                    event_type=operation_name,
                    target=target,
                    error_type=type(e).__name__
                ).inc()
                raise
        return wrapper
    return decorator


def get_metrics():
    """Get current metrics in Prometheus format.
    
    Returns:
        bytes: Prometheus metrics data
    """
    return generate_latest()


def get_metrics_content_type():
    """Get the content type for Prometheus metrics.
    
    Returns:
        str: Content type header value
    """
    return CONTENT_TYPE_LATEST


def reset_metrics():
    """Reset all metrics. Useful for testing."""
    EVENTS_SUBMITTED.clear()
    EVENTS_SUCCESS.clear()
    EVENTS_FAILURE.clear()
    BATCH_SUBMISSIONS.clear()
    REQUEST_DURATION.clear()
    BATCH_SIZE.clear()
    ACTIVE_CONNECTIONS.set(0)
