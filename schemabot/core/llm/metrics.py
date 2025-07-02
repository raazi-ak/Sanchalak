"""
LLM Performance Metrics and Monitoring for Sanchalak.

This module provides comprehensive metrics collection, performance monitoring,
and analytics for LLM operations in the government scheme eligibility bot.
"""

import time
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
import statistics
from collections import defaultdict, deque

import structlog
from prometheus_client import Counter, Histogram, Gauge, Summary, Info
import psutil

logger = structlog.get_logger(__name__)


class MetricType(Enum):
    """Types of metrics we collect."""
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    GAUGE = "gauge"
    SUMMARY = "summary"


class LLMOperation(Enum):
    """Types of LLM operations we track."""
    GENERATE_RESPONSE = "generate_response"
    VALIDATE_RESPONSE = "validate_response"
    EXTRACT_DATA = "extract_data"
    CLASSIFY_INTENT = "classify_intent"
    GENERATE_FOLLOWUP = "generate_followup"


@dataclass
class RequestMetrics:
    """Metrics for a single LLM request."""
    operation: LLMOperation
    start_time: float
    end_time: Optional[float] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    model_name: str = ""
    success: bool = False
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    response_quality_score: Optional[float] = None
    cache_hit: bool = False
    retries: int = 0
    conversation_id: Optional[str] = None
    user_language: str = "hi"

    @property
    def duration_ms(self) -> float:
        """Calculate request duration in milliseconds."""
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000

    @property
    def tokens_per_second(self) -> float:
        """Calculate tokens per second generation rate."""
        if self.end_time is None or self.tokens_output is None:
            return 0.0
        duration = self.end_time - self.start_time
        return self.tokens_output / duration if duration > 0 else 0.0


@dataclass
class AggregatedMetrics:
    """Aggregated metrics over a time period."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    avg_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0
    avg_tokens_per_second: float = 0.0
    cache_hit_rate: float = 0.0
    avg_quality_score: float = 0.0
    error_rate: float = 0.0
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    operations_by_type: Dict[str, int] = field(default_factory=dict)
    languages_distribution: Dict[str, int] = field(default_factory=dict)


class LLMMetricsCollector:
    """Collects and manages LLM performance metrics."""

    def __init__(self, max_history_size: int = 10000):
        self.max_history_size = max_history_size
        self.request_history: deque = deque(maxlen=max_history_size)
        self.active_requests: Dict[str, RequestMetrics] = {}

        # Initialize Prometheus metrics
        self._init_prometheus_metrics()

        # Performance tracking
        self.hourly_metrics: Dict[str, AggregatedMetrics] = {}
        self.daily_metrics: Dict[str, AggregatedMetrics] = {}

        # System metrics
        self.system_metrics = {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "gpu_usage": 0.0,
            "gpu_memory": 0.0
        }

        logger.info("LLM metrics collector initialized")

    def _init_prometheus_metrics(self):
        """Initialize Prometheus metrics."""

        # Request metrics
        self.request_counter = Counter(
            'llm_requests_total',
            'Total LLM requests',
            ['operation', 'model', 'language', 'status']
        )

        self.request_duration = Histogram(
            'llm_request_duration_seconds',
            'LLM request duration in seconds',
            ['operation', 'model'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
        )

        self.tokens_processed = Counter(
            'llm_tokens_processed_total',
            'Total tokens processed',
            ['direction', 'model', 'operation']  # direction: input/output
        )

        self.response_quality = Histogram(
            'llm_response_quality_score',
            'LLM response quality scores',
            ['operation', 'model'],
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        )

        self.cache_hits = Counter(
            'llm_cache_hits_total',
            'LLM cache hits',
            ['operation', 'model']
        )

        self.retries = Counter(
            'llm_retries_total',
            'LLM request retries',
            ['operation', 'model', 'error_type']
        )

        # Current state metrics
        self.active_requests_gauge = Gauge(
            'llm_active_requests',
            'Currently active LLM requests'
        )

        self.tokens_per_second = Gauge(
            'llm_tokens_per_second',
            'Current tokens per second rate',
            ['model']
        )

        # System metrics
        self.system_cpu = Gauge('llm_system_cpu_usage_percent', 'CPU usage percentage')
        self.system_memory = Gauge('llm_system_memory_usage_percent', 'Memory usage percentage')
        self.system_gpu = Gauge('llm_system_gpu_usage_percent', 'GPU usage percentage')
        self.system_gpu_memory = Gauge('llm_system_gpu_memory_usage_percent', 'GPU memory usage')

        # Model info
        self.model_info = Info('llm_model_info', 'LLM model information')

    def start_request(
        self,
        operation: LLMOperation,
        model_name: str,
        conversation_id: Optional[str] = None,
        user_language: str = "hi",
        tokens_input: Optional[int] = None
    ) -> str:
        """
        Start tracking a new LLM request.

        Args:
            operation: Type of LLM operation
            model_name: Name of the model being used
            conversation_id: ID of the conversation
            user_language: User's language preference
            tokens_input: Number of input tokens

        Returns:
            str: Request tracking ID
        """
        request_id = f"{operation.value}_{int(time.time() * 1000000)}"

        metrics = RequestMetrics(
            operation=operation,
            start_time=time.time(),
            model_name=model_name,
            conversation_id=conversation_id,
            user_language=user_language,
            tokens_input=tokens_input
        )

        self.active_requests[request_id] = metrics
        self.active_requests_gauge.set(len(self.active_requests))

        logger.debug(
            "Started LLM request tracking",
            request_id=request_id,
            operation=operation.value,
            model=model_name
        )

        return request_id

    def finish_request(
        self,
        request_id: str,
        success: bool = True,
        tokens_output: Optional[int] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        response_quality_score: Optional[float] = None,
        cache_hit: bool = False,
        retries: int = 0
    ):
        """
        Finish tracking an LLM request.

        Args:
            request_id: Request tracking ID
            success: Whether the request was successful
            tokens_output: Number of output tokens generated
            error_type: Type of error if failed
            error_message: Error message if failed
            response_quality_score: Quality score (0-1)
            cache_hit: Whether response came from cache
            retries: Number of retries performed
        """
        if request_id not in self.active_requests:
            logger.warning(f"Request ID not found: {request_id}")
            return

        metrics = self.active_requests.pop(request_id)
        metrics.end_time = time.time()
        metrics.success = success
        metrics.tokens_output = tokens_output
        metrics.error_type = error_type
        metrics.error_message = error_message
        metrics.response_quality_score = response_quality_score
        metrics.cache_hit = cache_hit
        metrics.retries = retries

        # Add to history
        self.request_history.append(metrics)

        # Update Prometheus metrics
        self._update_prometheus_metrics(metrics)

        # Update gauges
        self.active_requests_gauge.set(len(self.active_requests))

        if tokens_output and metrics.duration_ms > 0:
            tokens_per_sec = metrics.tokens_per_second
            self.tokens_per_second.labels(model=metrics.model_name).set(tokens_per_sec)

        logger.debug(
            "Finished LLM request tracking",
            request_id=request_id,
            duration_ms=metrics.duration_ms,
            success=success,
            tokens_output=tokens_output
        )

    def _update_prometheus_metrics(self, metrics: RequestMetrics):
        """Update Prometheus metrics with request data."""

        # Request counter
        status = "success" if metrics.success else "error"
        self.request_counter.labels(
            operation=metrics.operation.value,
            model=metrics.model_name,
            language=metrics.user_language,
            status=status
        ).inc()

        # Duration histogram
        duration_seconds = metrics.duration_ms / 1000.0
        self.request_duration.labels(
            operation=metrics.operation.value,
            model=metrics.model_name
        ).observe(duration_seconds)

        # Token counters
        if metrics.tokens_input:
            self.tokens_processed.labels(
                direction="input",
                model=metrics.model_name,
                operation=metrics.operation.value
            ).inc(metrics.tokens_input)

        if metrics.tokens_output:
            self.tokens_processed.labels(
                direction="output",
                model=metrics.model_name,
                operation=metrics.operation.value
            ).inc(metrics.tokens_output)

        # Quality score
        if metrics.response_quality_score is not None:
            self.response_quality.labels(
                operation=metrics.operation.value,
                model=metrics.model_name
            ).observe(metrics.response_quality_score)

        # Cache hits
        if metrics.cache_hit:
            self.cache_hits.labels(
                operation=metrics.operation.value,
                model=metrics.model_name
            ).inc()

        # Retries
        if metrics.retries > 0:
            self.retries.labels(
                operation=metrics.operation.value,
                model=metrics.model_name,
                error_type=metrics.error_type or "unknown"
            ).inc(metrics.retries)

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current real-time metrics."""
        return {
            "active_requests": len(self.active_requests),
            "total_requests_today": len([
                m for m in self.request_history
                if datetime.fromtimestamp(m.start_time).date() == datetime.now().date()
            ]),
            "system_metrics": self.system_metrics.copy(),
            "cache_hit_rate_last_hour": self._calculate_cache_hit_rate(hours=1),
            "avg_response_time_last_hour": self._calculate_avg_response_time(hours=1),
            "error_rate_last_hour": self._calculate_error_rate(hours=1)
        }

    def get_aggregated_metrics(self, hours: int = 24) -> AggregatedMetrics:
        """Get aggregated metrics for the specified time period."""
        cutoff_time = time.time() - (hours * 3600)
        recent_requests = [
            m for m in self.request_history
            if m.start_time >= cutoff_time and m.end_time is not None
        ]

        if not recent_requests:
            return AggregatedMetrics()

        # Calculate aggregated metrics
        total_requests = len(recent_requests)
        successful_requests = len([m for m in recent_requests if m.success])
        failed_requests = total_requests - successful_requests

        response_times = [m.duration_ms for m in recent_requests]
        tokens_input = sum(m.tokens_input or 0 for m in recent_requests)
        tokens_output = sum(m.tokens_output or 0 for m in recent_requests)

        cache_hits = len([m for m in recent_requests if m.cache_hit])
        quality_scores = [m.response_quality_score for m in recent_requests if m.response_quality_score is not None]

        # Error analysis
        errors_by_type = defaultdict(int)
        for m in recent_requests:
            if not m.success and m.error_type:
                errors_by_type[m.error_type] += 1

        # Operation distribution
        operations_by_type = defaultdict(int)
        for m in recent_requests:
            operations_by_type[m.operation.value] += 1

        # Language distribution
        languages_distribution = defaultdict(int)
        for m in recent_requests:
            languages_distribution[m.user_language] += 1

        return AggregatedMetrics(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            total_tokens_input=tokens_input,
            total_tokens_output=tokens_output,
            avg_response_time_ms=statistics.mean(response_times) if response_times else 0.0,
            p95_response_time_ms=statistics.quantiles(response_times, n=20)[18] if len(response_times) > 1 else 0.0,
            p99_response_time_ms=statistics.quantiles(response_times, n=100)[98] if len(response_times) > 1 else 0.0,
            avg_tokens_per_second=statistics.mean([m.tokens_per_second for m in recent_requests if m.tokens_per_second > 0]) if recent_requests else 0.0,
            cache_hit_rate=cache_hits / total_requests if total_requests > 0 else 0.0,
            avg_quality_score=statistics.mean(quality_scores) if quality_scores else 0.0,
            error_rate=failed_requests / total_requests if total_requests > 0 else 0.0,
            errors_by_type=dict(errors_by_type),
            operations_by_type=dict(operations_by_type),
            languages_distribution=dict(languages_distribution)
        )

    def _calculate_cache_hit_rate(self, hours: int) -> float:
        """Calculate cache hit rate for the specified period."""
        cutoff_time = time.time() - (hours * 3600)
        recent_requests = [m for m in self.request_history if m.start_time >= cutoff_time]

        if not recent_requests:
            return 0.0

        cache_hits = len([m for m in recent_requests if m.cache_hit])
        return cache_hits / len(recent_requests)

    def _calculate_avg_response_time(self, hours: int) -> float:
        """Calculate average response time for the specified period."""
        cutoff_time = time.time() - (hours * 3600)
        recent_requests = [
            m for m in self.request_history
            if m.start_time >= cutoff_time and m.end_time is not None
        ]

        if not recent_requests:
            return 0.0

        response_times = [m.duration_ms for m in recent_requests]
        return statistics.mean(response_times)

    def _calculate_error_rate(self, hours: int) -> float:
        """Calculate error rate for the specified period."""
        cutoff_time = time.time() - (hours * 3600)
        recent_requests = [m for m in self.request_history if m.start_time >= cutoff_time]

        if not recent_requests:
            return 0.0

        failed_requests = len([m for m in recent_requests if not m.success])
        return failed_requests / len(recent_requests)

    async def update_system_metrics(self):
        """Update system resource metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.system_metrics["cpu_usage"] = cpu_percent
            self.system_cpu.set(cpu_percent)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            self.system_metrics["memory_usage"] = memory_percent
            self.system_memory.set(memory_percent)

            # GPU metrics (if available)
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]  # Use first GPU
                    gpu_usage = gpu.load * 100
                    gpu_memory = gpu.memoryUtil * 100

                    self.system_metrics["gpu_usage"] = gpu_usage
                    self.system_metrics["gpu_memory"] = gpu_memory
                    self.system_gpu.set(gpu_usage)
                    self.system_gpu_memory.set(gpu_memory)
            except ImportError:
                # GPU monitoring not available
                pass

        except Exception as e:
            logger.error(f"Error updating system metrics: {e}")

    def export_metrics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Export comprehensive metrics summary."""
        aggregated = self.get_aggregated_metrics(hours)
        current = self.get_current_metrics()

        return {
            "timestamp": datetime.now().isoformat(),
            "period_hours": hours,
            "aggregated_metrics": {
                "total_requests": aggregated.total_requests,
                "success_rate": (aggregated.successful_requests / aggregated.total_requests) if aggregated.total_requests > 0 else 0.0,
                "error_rate": aggregated.error_rate,
                "avg_response_time_ms": aggregated.avg_response_time_ms,
                "p95_response_time_ms": aggregated.p95_response_time_ms,
                "p99_response_time_ms": aggregated.p99_response_time_ms,
                "cache_hit_rate": aggregated.cache_hit_rate,
                "avg_quality_score": aggregated.avg_quality_score,
                "tokens_processed": {
                    "input": aggregated.total_tokens_input,
                    "output": aggregated.total_tokens_output,
                    "total": aggregated.total_tokens_input + aggregated.total_tokens_output
                },
                "avg_tokens_per_second": aggregated.avg_tokens_per_second
            },
            "current_metrics": current,
            "distributions": {
                "errors_by_type": aggregated.errors_by_type,
                "operations_by_type": aggregated.operations_by_type,
                "languages_distribution": aggregated.languages_distribution
            }
        }


# Global metrics collector instance
metrics_collector = LLMMetricsCollector()


# Decorator for automatic metrics collection
def track_llm_operation(operation: LLMOperation, model_name: str = ""):
    """Decorator to automatically track LLM operations."""
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            # Extract conversation_id and language if available
            conversation_id = kwargs.get('conversation_id')
            user_language = kwargs.get('language', 'hi')
            tokens_input = kwargs.get('tokens_input')

            request_id = metrics_collector.start_request(
                operation=operation,
                model_name=model_name,
                conversation_id=conversation_id,
                user_language=user_language,
                tokens_input=tokens_input
            )

            try:
                result = await func(*args, **kwargs)

                # Extract metrics from result if it's a dict
                tokens_output = None
                quality_score = None
                cache_hit = False

                if isinstance(result, dict):
                    tokens_output = result.get('tokens_output')
                    quality_score = result.get('quality_score')
                    cache_hit = result.get('cache_hit', False)

                metrics_collector.finish_request(
                    request_id=request_id,
                    success=True,
                    tokens_output=tokens_output,
                    response_quality_score=quality_score,
                    cache_hit=cache_hit
                )

                return result

            except Exception as e:
                metrics_collector.finish_request(
                    request_id=request_id,
                    success=False,
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                raise

        return wrapper
    return decorator


if __name__ == "__main__":
    # Example usage
    import asyncio

    async def test_metrics():
        # Test metrics collection
        request_id = metrics_collector.start_request(
            operation=LLMOperation.GENERATE_RESPONSE,
            model_name="gemma-2b-it",
            tokens_input=100
        )

        # Simulate work
        await asyncio.sleep(0.5)

        metrics_collector.finish_request(
            request_id=request_id,
            success=True,
            tokens_output=150,
            response_quality_score=0.85,
            cache_hit=False
        )

        # Get metrics
        current = metrics_collector.get_current_metrics()
        aggregated = metrics_collector.get_aggregated_metrics(hours=1)

        print("Current metrics:", current)
        print("Aggregated metrics:", aggregated)

    asyncio.run(test_metrics())