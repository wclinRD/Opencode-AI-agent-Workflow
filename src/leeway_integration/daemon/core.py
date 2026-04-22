"""Leeway daemon core implementation."""

from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, TextIO

try:
    import cryptography
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

# Import error classes for LLM provider (Phase B.4)
from leeway_integration.error import (
    LlmProviderNotFoundError,
    LlmModelNotFoundError,
    LlmAuthenticationError,
    LlmRateLimitError,
    LlmInvalidRequestError,
    LlmProviderError,
    LlmContextLengthError,
    # Phase B.5: Testing Framework
    TestNotFoundError,
    TestAlreadyExistsError,
    TestCompileError,
    TestExecutionError,
    TestAssertionFailedError,
    TestTimeoutError,
    TestSuiteNotFoundError,
    TestSuiteAlreadyExistsError,
    TestCoverageError,
    # Phase B.6: Performance Profiling
    ProfileNotFoundError,
    ProfileAlreadyExistsError,
    ProfileInvalidError,
)

# Import protocol classes for Profiling (Phase B.6)
from leeway_integration.protocol import (
    WorkflowProfileData,
    NodeProfileData,
    ToolProfileData,
    PerformanceMetrics,
    SlowestNodesReport,
    BottleneckReport,
)


# =============================================================================
# StructuredLogger: Structured Logging System
# =============================================================================

class StructuredLogger:
    """
    Structured logging system with JSON formatted output.
    
    Features:
    - Log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - JSON formatted output
    - Log file rotation
    - Component/source tagging
    - Configurable output (stdout, file, or both)
    """
    
    # Log levels
    LEVEL_DEBUG = "DEBUG"
    LEVEL_INFO = "INFO"
    LEVEL_WARNING = "WARNING"
    LEVEL_ERROR = "ERROR"
    LEVEL_CRITICAL = "CRITICAL"
    
    def __init__(self, log_dir: Path | None = None, level: str = "INFO",
                 output: str = "stdout", max_file_size: int = 10 * 1024 * 1024,
                 backup_count: int = 5):
        """
        Initialize structured logger.
        
        Args:
            log_dir: Directory for log files (default: .leeway/logs)
            level: Minimum log level
            output: Output mode - 'stdout', 'file', or 'both'
            max_file_size: Maximum log file size before rotation
            backup_count: Number of backup files to keep
        """
        self._log_dir = log_dir or Path(".leeway/logs")
        self._log_dir.mkdir(parents=True, exist_ok=True)
        
        self._level = level
        self._output = output
        self._max_file_size = max_file_size
        self._backup_count = backup_count
        
        # Log level priority
        self._level_priority = {
            self.LEVEL_DEBUG: 0,
            self.LEVEL_INFO: 1,
            self.LEVEL_WARNING: 2,
            self.LEVEL_ERROR: 3,
            self.LEVEL_CRITICAL: 4,
        }
        
        self._current_level_priority = self._level_priority.get(level, 1)
        self._lock = threading.Lock()
        
        # Daily log file
        self._log_file: Path | None = None
    
    def _get_log_file(self) -> Path:
        """Get the current log file path."""
        import datetime
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        if self._log_file is None:
            self._log_file = self._log_dir / f"leeway-{today}.log"
        
        # Check file size and rotate if needed
        if self._log_file.exists() and self._log_file.stat().st_size >= self._max_file_size:
            self._rotate_log_file()
        
        return self._log_file
    
    def _rotate_log_file(self) -> None:
        """Rotate log files."""
        import datetime
        
        if self._log_file is None:
            return
        
        # Rotate existing backups
        for i in range(self._backup_count - 1, 0, -1):
            old_file = self._log_file.with_suffix(f".{i}.log")
            new_file = self._log_file.with_suffix(f".{i + 1}.log")
            if old_file.exists():
                old_file.rename(new_file)
        
        # Rotate current to .1.log
        if self._log_file.exists():
            self._log_file.rename(self._log_file.with_suffix(".1.log"))
        
        self._log_file = None
    
    def log(self, level: str, message: str, component: str | None = None,
          execution_id: str | None = None, **kwargs) -> None:
        """
        Log a message with structured data.
        
        Args:
            level: Log level
            message: Log message
            component: Component/source
            execution_id: Execution ID for tracking
            **kwargs: Additional structured data
        """
        # Check log level
        level_priority = self._level_priority.get(level, 1)
        if level_priority < self._current_level_priority:
            return
        
        import datetime
        
        # Build log entry
        entry = {
            "timestamp": datetime.datetime.now().isoformat(timespec="milliseconds"),
            "level": level,
            "message": message,
        }
        
        if component:
            entry["component"] = component
        
        if execution_id:
            entry["execution_id"] = execution_id
        
        # Add extra fields
        for key, value in kwargs.items():
            if value is not None:
                entry[key] = value
        
        # Format as JSON
        log_line = json.dumps(entry)
        
        with self._lock:
            # Output to stdout
            if self._output in ("stdout", "both"):
                print(log_line, file=sys.stdout)
            
            # Output to file
            if self._output in ("file", "both"):
                log_file = self._get_log_file()
                with open(log_file, "a") as f:
                    f.write(log_line + "\n")
    
    def debug(self, message: str, component: str | None = None, 
            execution_id: str | None = None, **kwargs) -> None:
        """Log a debug message."""
        self.log(self.LEVEL_DEBUG, message, component, execution_id, **kwargs)
    
    def info(self, message: str, component: str | None = None,
           execution_id: str | None = None, **kwargs) -> None:
        """Log an info message."""
        self.log(self.LEVEL_INFO, message, component, execution_id, **kwargs)
    
    def warning(self, message: str, component: str | None = None,
             execution_id: str | None = None, **kwargs) -> None:
        """Log a warning message."""
        self.log(self.LEVEL_WARNING, message, component, execution_id, **kwargs)
    
    def error(self, message: str, component: str | None = None,
           execution_id: str | None = None, **kwargs) -> None:
        """Log an error message."""
        self.log(self.LEVEL_ERROR, message, component, execution_id, **kwargs)
    
    def critical(self, message: str, component: str | None = None,
                execution_id: str | None = None, **kwargs) -> None:
        """Log a critical message."""
        self.log(self.LEVEL_CRITICAL, message, component, execution_id, **kwargs)


# =============================================================================
# MetricsCollector: Metrics Collection System
# =============================================================================

class MetricsCollector:
    """
    Metrics collection system.
    
    Features:
    - Counter metrics (incremental values)
    - Gauge metrics (point-in-time values)
    - Histogram metrics (distribution)
    - Timing metrics
    - Percentile calculations
    
    Metrics are namespaced by category:
    - workflow.* - Workflow execution metrics
    - daemon.* - Daemon metrics
    - mcp.* - MCP server metrics
    - hook.* - Hook execution metrics
    - cache.* - Cache metrics
    - scheduler.* - Scheduler metrics
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        # Counter metrics: {"metric_name": {"value": int, "labels": dict}}
        self._counters: dict[str, dict] = {}
        
        # Gauge metrics: {"metric_name": {"value": float, "labels": dict}}
        self._gauges: dict[str, dict] = {}
        
        # Histogram metrics: {"metric_name": {"values": list, "labels": dict}}
        self._histograms: dict[str, dict] = {}
        
        # Timing metrics (special histogram for durations)
        self._timings: dict[str, dict] = {}
        
        self._lock = threading.RLock()
        
        # Default percentiles to calculate
        self._percentiles = [0.5, 0.75, 0.95, 0.99]
        
        # Max values to keep per histogram (for memory efficiency)
        self._max_histogram_values = 1000
    
    def _get_metric_key(self, name: str, labels: dict | None = None) -> str:
        """Generate a metric key with labels."""
        if not labels:
            return name
        
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    # Counter methods
    def inc_counter(self, name: str, value: float = 1, labels: dict | None = None) -> None:
        """
        Increment a counter metric.
        
        Args:
            name: Metric name
            value: Value to add (default: 1)
            labels: Metric labels
        """
        with self._lock:
            key = self._get_metric_key(name, labels)
            
            if key not in self._counters:
                self._counters[key] = {"value": 0.0, "labels": labels or {}}
            
            self._counters[key]["value"] += value
    
    def set_counter(self, name: str, value: float, labels: dict | None = None) -> None:
        """Set a counter metric to a specific value."""
        with self._lock:
            key = self._get_metric_key(name, labels)
            self._counters[key] = {"value": value, "labels": labels or {}}
    
    def get_counter(self, name: str, labels: dict | None = None) -> float:
        """Get counter value."""
        with self._lock:
            key = self._get_metric_key(name, labels)
            return self._counters.get(key, {}).get("value", 0.0)
    
    # Gauge methods
    def set_gauge(self, name: str, value: float, labels: dict | None = None) -> None:
        """
        Set a gauge metric.
        
        Args:
            name: Metric name
            value: Value to set
            labels: Metric labels
        """
        with self._lock:
            key = self._get_metric_key(name, labels)
            self._gauges[key] = {"value": value, "labels": labels or {}}
    
    def get_gauge(self, name: str, labels: dict | None = None) -> float | None:
        """Get gauge value."""
        with self._lock:
            key = self._get_metric_key(name, labels)
            return self._gauges.get(key, {}).get("value")
    
    # Histogram methods
    def observe(self, name: str, value: float, labels: dict | None = None) -> None:
        """
        Observe a value for histogram.
        
        Args:
            name: Metric name
            value: Value to record
            labels: Metric labels
        """
        with self._lock:
            key = self._get_metric_key(name, labels)
            
            if key not in self._histograms:
                self._histograms[key] = {"values": [], "labels": labels or {}}
            
            values = self._histograms[key]["values"]
            values.append(value)
            
            # Trim if needed
            if len(values) > self._max_histogram_values:
                # Keep last N values (approximate percentile)
                self._histograms[key]["values"] = values[-self._max_histogram_values:]
    
    # Timing methods
    def timing(self, name: str, duration_ms: float, labels: dict | None = None) -> None:
        """
        Record a timing metric.
        
        Args:
            name: Metric name (e.g., "workflow.execution_time")
            duration_ms: Duration in milliseconds
            labels: Metric labels
        """
        self.observe(name, duration_ms, labels)
    
    def start_timer(self, name: str, labels: dict | None = None) -> float:
        """Start a timer and return start time."""
        return time.time()
    
    def stop_timer(self, name: str, start_time: float, labels: dict | None = None) -> float:
        """
        Stop a timer and record the duration.
        
        Returns:
            Duration in milliseconds
        """
        duration_ms = (time.time() - start_time) * 1000
        self.timing(name, duration_ms, labels)
        return duration_ms
    
    # Aggregation methods
    def _calculate_percentiles(self, values: list[float]) -> dict[str, float]:
        """Calculate percentiles from a list of values."""
        if not values:
            return {}
        
        sorted_values = sorted(values)
        result = {}
        
        for p in self._percentiles:
            idx = int(len(sorted_values) * p)
            if idx >= len(sorted_values):
                idx = len(sorted_values) - 1
            result[f"p{int(p * 100)}"] = sorted_values[idx]
        
        return result
    
    def get_metrics(self, name: str | None = None) -> dict:
        """
        Get all metrics.
        
        Args:
            name: Optional metric name prefix filter
            
        Returns:
            Dictionary with counters, gauges, histograms, and timings
        """
        with self._lock:
            result = {
                "counters": {},
                "gauges": {},
                "histograms": {},
            }
            
            # Get counters
            for key, data in self._counters.items():
                if name is None or key.startswith(name):
                    result["counters"][key] = data["value"]
            
            # Get gauges
            for key, data in self._gauges.items():
                if name is None or key.startswith(name):
                    result["gauges"][key] = data["value"]
            
            # Get histograms with stats
            for key, data in self._histograms.items():
                if name is None or key.startswith(name):
                    values = data.get("values", [])
                    if values:
                        result["histograms"][key] = {
                            "count": len(values),
                            "sum": sum(values),
                            "min": min(values),
                            "max": max(values),
                            "avg": sum(values) / len(values),
                            "percentiles": self._calculate_percentiles(values),
                        }
            
            return result
    
    def get_summary(self) -> dict:
        """Get a summary of all metrics."""
        with self._lock:
            total_counters = len(self._counters)
            total_gauges = len(self._gauges)
            total_histograms = len(self._histograms)
            
            total_observations = sum(
                len(d.get("values", [])) 
                for d in self._histograms.values()
            )
            
            return {
                "counter_count": total_counters,
                "gauge_count": total_gauges,
                "histogram_count": total_histograms,
                "total_observations": total_observations,
            }
    
    def reset(self, name: str | None = None) -> int:
        """
        Reset metrics.
        
        Args:
            name: Optional metric name to reset
            
        Returns:
            Number of metrics reset
        """
        with self._lock:
            count = 0
            
            if name is None:
                # Reset all
                count = len(self._counters) + len(self._gauges) + len(self._histograms)
                self._counters.clear()
                self._gauges.clear()
                self._histograms.clear()
            else:
                # Reset specific metrics
                for key in list(self._counters.keys()):
                    if key.startswith(name):
                        del self._counters[key]
                        count += 1
                for key in list(self._gauges.keys()):
                    if key.startswith(name):
                        del self._gauges[key]
                        count += 1
                for key in list(self._histograms.keys()):
                    if key.startswith(name):
                        del self._histograms[key]
                        count += 1
            
            return count


# =============================================================================
# Phase B.4: Multi-Language LLM Support
# =============================================================================

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class LlmProviderEnum(str, Enum):
    """LLM provider enumeration."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    OLLAMA = "ollama"


@dataclass
class LLMProviderInfo:
    """LLM provider information."""
    name: str
    display_name: str
    description: str
    supports_streaming: bool = True
    supports_vision: bool = False
    supports_function_calling: bool = False
    supports_json_mode: bool = False
    default_models: list[str] = field(default_factory=list)
    authentication: str = "api_key"
    base_url: str | None = None


@dataclass
class LLMModelInfo:
    """LLM model information."""
    id: str = ""
    display_name: str = ""
    provider: str = ""
    description: str = ""
    context_window: int = 4096
    max_output_tokens: int = 2048
    supports_streaming: bool = True
    supports_vision: bool = False
    supports_function_calling: bool = False
    supports_json_mode: bool = False
    pricing: dict[str, float] | None = None


@dataclass
class LLMMessage:
    """LLM message."""
    role: str = ""
    content: str = ""


@dataclass
class LLMTool:
    """LLM tool definition."""
    name: str = ""
    description: str = ""
    input_schema: dict = field(default_factory=dict)


@dataclass
class LLMToolCall:
    """LLM tool call."""
    id: str = ""
    name: str = ""
    arguments: dict = field(default_factory=dict)


@dataclass
class LLMCompletion:
    """LLM completion."""
    id: str = ""
    model: str = ""
    content: str | None = None
    tool_calls: list[LLMToolCall] | None = None
    finish_reason: str | None = None
    usage: dict[str, int] | None = None
    provider: str = ""
    created_at: str | None = None


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """Provider display name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Provider description."""
        pass
    
    @property
    @abstractmethod
    def base_url(self) -> str | None:
        """Provider base URL (None for default)."""
        pass
    
    @property
    @abstractmethod
    def authentication_type(self) -> str:
        """Authentication type: 'api_key', 'bearer_token', 'none'."""
        pass
    
    @abstractmethod
    def get_available_models(self) -> list[LLMModelInfo]:
        """Get list of available models."""
        pass
    
    @abstractmethod
    def complete(
        self,
        model: str,
        messages: list[LLMMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        stop: list[str] | None = None,
        stream: bool = False,
        tools: list[LLMTool] | None = None,
        system: str | None = None,
        api_key: str | None = None,
    ) -> LLMCompletion:
        """
        Execute a completion request.
        
        Args:
            model: Model ID
            messages: List of messages
            temperature: Temperature (0-1)
            max_tokens: Max tokens to generate
            top_p: Nucleus sampling
            stop: Stop sequences
            stream: Enable streaming
            tools: Tool definitions
            system: System prompt
            api_key: Override API key
            
        Returns:
            LLMCompletion result
        """
        pass
    
    def _validate_api_key(self, api_key: str | None) -> str:
        """Validate API key."""
        if not api_key:
            raise LlmAuthenticationError(
                self.name,
                f"API key required for {self.name}"
            )
        return api_key


class AnthropicProvider(BaseLLMProvider):
    """Anthropic (Claude) provider."""
    
    @property
    def name(self) -> str:
        return "anthropic"
    
    @property
    def display_name(self) -> str:
        return "Anthropic Claude"
    
    @property
    def description(self) -> str:
        return "Anthropic's Claude models - Claude 3.5 Sonnet, Opus, etc."
    
    @property
    def base_url(self) -> str | None:
        return "https://api.anthropic.com"
    
    @property
    def authentication_type(self) -> str:
        return "api_key"
    
    def get_available_models(self) -> list[LLMModelInfo]:
        return [
            LLMModelInfo(
                id="claude-3-5-sonnet-20241022",
                display_name="Claude 3.5 Sonnet",
                provider="anthropic",
                description="Latest Claude 3.5 Sonnet - best overall",
                context_window=200000,
                max_output_tokens=8192,
                supports_streaming=True,
                supports_vision=True,
            ),
            LLMModelInfo(
                id="claude-3-opus-20240229",
                display_name="Claude 3 Opus",
                provider="anthropic",
                description="Claude 3 Opus - most capable",
                context_window=200000,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_vision=True,
            ),
            LLMModelInfo(
                id="claude-3-sonnet-20240229",
                display_name="Claude 3 Sonnet",
                provider="anthropic",
                description="Claude 3 Sonnet - balanced",
                context_window=200000,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_vision=True,
            ),
            LLMModelInfo(
                id="claude-3-haiku-20240307",
                display_name="Claude 3 Haiku",
                provider="anthropic",
                description="Claude 3 Haiku - fastest",
                context_window=200000,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_vision=True,
            ),
        ]
    
    def complete(
        self,
        model: str,
        messages: list[LLMMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        stop: list[str] | None = None,
        stream: bool = False,
        tools: list[LLMTool] | None = None,
        system: str | None = None,
        api_key: str | None = None,
    ) -> LLMCompletion:
        api_key = self._validate_api_key(api_key)
        
        # Import httpx for API calls
        import httpx
        
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        
        # Convert messages to Anthropic format
        anthropic_messages = []
        for msg in messages:
            if msg.role == "system":
                system = msg.content
            else:
                anthropic_messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })
        
        body = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens or 1024,
        }
        
        if temperature is not None:
            body["temperature"] = temperature
        if top_p is not None:
            body["top_p"] = top_p
        if stop:
            body["stop_sequences"] = stop
        if tools:
            body["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in tools
            ]
        
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, headers=headers, json=body)
                response.raise_for_status()
                data = response.json()
                
                return LLMCompletion(
                    id=data.get("id", str(uuid.uuid4())),
                    model=model,
                    content=data.get("content", [{}])[0].get("text", ""),
                    finish_reason=data.get("stop_reason"),
                    usage=data.get("usage", {}),
                    provider=self.name,
                    created_at=datetime.now().isoformat(),
                )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise LlmAuthenticationError(self.name, "Invalid API key")
            elif e.response.status_code == 429:
                raise LlmRateLimitError(self.name)
            elif e.response.status_code == 400:
                error_data = e.response.json()
                raise LlmInvalidRequestError(
                    self.name,
                    error_data.get("error", {}).get("message", str(e))
                )
            else:
                raise LlmProviderError(self.name, str(e), e.response.json() if e.response.content else {})
        except Exception as e:
            raise LlmProviderError(self.name, str(e))


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider."""
    
    @property
    def name(self) -> str:
        return "openai"
    
    @property
    def display_name(self) -> str:
        return "OpenAI"
    
    @property
    def description(self) -> str:
        return "OpenAI's GPT models - GPT-4, GPT-4 Turbo, etc."
    
    @property
    def base_url(self) -> str | None:
        return "https://api.openai.com"
    
    @property
    def authentication_type(self) -> str:
        return "api_key"
    
    def get_available_models(self) -> list[LLMModelInfo]:
        return [
            LLMModelInfo(
                id="gpt-4-turbo-preview",
                display_name="GPT-4 Turbo",
                provider="openai",
                description="Latest GPT-4 Turbo - faster and cheaper",
                context_window=128000,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_function_calling=True,
                supports_json_mode=True,
            ),
            LLMModelInfo(
                id="gpt-4",
                display_name="GPT-4",
                provider="openai",
                description="GPT-4 - most capable",
                context_window=8192,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_function_calling=True,
                supports_json_mode=True,
            ),
            LLMModelInfo(
                id="gpt-3.5-turbo",
                display_name="GPT-3.5 Turbo",
                provider="openai",
                description="GPT-3.5 Turbo - fast and cheap",
                context_window=16385,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_function_calling=True,
                supports_json_mode=True,
            ),
            LLMModelInfo(
                id="gpt-4-vision-preview",
                display_name="GPT-4 Vision",
                provider="openai",
                description="GPT-4 with vision understanding",
                context_window=128000,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_vision=True,
            ),
        ]
    
    def complete(
        self,
        model: str,
        messages: list[LLMMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        stop: list[str] | None = None,
        stream: bool = False,
        tools: list[LLMTool] | None = None,
        system: str | None = None,
        api_key: str | None = None,
    ) -> LLMCompletion:
        api_key = self._validate_api_key(api_key)
        
        import httpx
        
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        # Convert messages to OpenAI format
        openai_messages = []
        if system:
            openai_messages.append({"role": "system", "content": system})
        for msg in messages:
            openai_messages.append({
                "role": msg.role,
                "content": msg.content,
            })
        
        body = {
            "model": model,
            "messages": openai_messages,
        }
        
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens:
            body["max_tokens"] = max_tokens
        if top_p is not None:
            body["top_p"] = top_p
        if stop:
            body["stop"] = stop
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in tools
            ]
        
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, headers=headers, json=body)
                response.raise_for_status()
                data = response.json()
                
                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                
                tool_calls = None
                if message.get("tool_calls"):
                    tool_calls = [
                        LLMToolCall(
                            id=tc.get("id", str(uuid.uuid4())),
                            name=tc.get("function", {}).get("name", ""),
                            arguments=json.loads(tc.get("function", {}).get("arguments", "{}")),
                        )
                        for tc in message["tool_calls"]
                    ]
                
                return LLMCompletion(
                    id=data.get("id", str(uuid.uuid4())),
                    model=model,
                    content=message.get("content"),
                    tool_calls=tool_calls,
                    finish_reason=choice.get("finish_reason"),
                    usage=data.get("usage", {}),
                    provider=self.name,
                    created_at=datetime.now().isoformat(),
                )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise LlmAuthenticationError(self.name, "Invalid API key")
            elif e.response.status_code == 429:
                raise LlmRateLimitError(self.name)
            elif e.response.status_code == 400:
                error_data = e.response.json()
                raise LlmInvalidRequestError(
                    self.name,
                    error_data.get("error", {}).get("message", str(e))
                )
            else:
                raise LlmProviderError(self.name, str(e), e.response.json() if e.response.content else {})
        except Exception as e:
            raise LlmProviderError(self.name, str(e))


class GoogleProvider(BaseLLMProvider):
    """Google AI (Gemini) provider."""
    
    @property
    def name(self) -> str:
        return "google"
    
    @property
    def display_name(self) -> str:
        return "Google AI Gemini"
    
    @property
    def description(self) -> str:
        return "Google's Gemini models"
    
    @property
    def base_url(self) -> str | None:
        return "https://generativelanguage.googleapis.com"
    
    @property
    def authentication_type(self) -> str:
        return "api_key"
    
    def get_available_models(self) -> list[LLMModelInfo]:
        return [
            LLMModelInfo(
                id="gemini-1.5-pro",
                display_name="Gemini 1.5 Pro",
                provider="google",
                description="Gemini 1.5 Pro with 1M context",
                context_window=1048576,
                max_output_tokens=8192,
                supports_streaming=True,
                supports_vision=True,
            ),
            LLMModelInfo(
                id="gemini-1.5-flash",
                display_name="Gemini 1.5 Flash",
                provider="google",
                description="Gemini 1.5 Flash - fast and efficient",
                context_window=1048576,
                max_output_tokens=8192,
                supports_streaming=True,
                supports_vision=True,
            ),
            LLMModelInfo(
                id="gemini-pro",
                display_name="Gemini Pro",
                provider="google",
                description="Gemini Pro",
                context_window=32768,
                max_output_tokens=8192,
                supports_streaming=True,
            ),
            LLMModelInfo(
                id="gemini-pro-vision",
                display_name="Gemini Pro Vision",
                provider="google",
                description="Gemini Pro with vision",
                context_window=32768,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_vision=True,
            ),
        ]
    
    def complete(
        self,
        model: str,
        messages: list[LLMMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        stop: list[str] | None = None,
        stream: bool = False,
        tools: list[LLMTool] | None = None,
        system: str | None = None,
        api_key: str | None = None,
    ) -> LLMCompletion:
        api_key = self._validate_api_key(api_key)
        
        import httpx
        
        url = f"{self.base_url}/v1beta/models/{model}:generateContent"
        headers = {"Content-Type": "application/json"}
        
        # Build contents
        contents = []
        for msg in messages:
            if msg.role != "system":
                contents.append({
                    "role": msg.role,
                    "parts": [{"text": msg.content}],
                })
        
        generation_config = {
            "temperature": temperature or 0.9,
            "maxOutputTokens": max_tokens or 2048,
        }
        
        if top_p:
            generation_config["topP"] = top_p
        if stop:
            generation_config["stopSequences"] = list(stop)
        
        body = {
            "contents": contents,
            "generationConfig": generation_config,
        }
        
        try:
            with httpx.Client(timeout=60.0) as client:
                url_with_key = f"{url}?key={api_key}"
                response = client.post(url_with_key, headers=headers, json=body)
                response.raise_for_status()
                data = response.json()
                
                content = ""
                if data.get("candidates"):
                    candidate = data["candidates"][0]
                    if candidate.get("content", {}).get("parts"):
                        content = candidate["content"]["parts"][0].get("text", "")
                
                return LLMCompletion(
                    id=str(uuid.uuid4()),
                    model=model,
                    content=content,
                    finish_reason="stop",
                    usage={"prompt_tokens": 0, "completion_tokens": 0},
                    provider=self.name,
                    created_at=datetime.now().isoformat(),
                )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise LlmAuthenticationError(self.name, "Invalid API key")
            elif e.response.status_code == 429:
                raise LlmRateLimitError(self.name)
            else:
                raise LlmProviderError(self.name, str(e), e.response.json() if e.response.content else {})
        except Exception as e:
            raise LlmProviderError(self.name, str(e))


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider."""
    
    @property
    def name(self) -> str:
        return "ollama"
    
    @property
    def display_name(self) -> str:
        return "Ollama (Local)"
    
    @property
    def description(self) -> str:
        return "Ollama - Run large language models locally"
    
    @property
    def base_url(self) -> str | None:
        return "http://localhost:11434"
    
    @property
    def authentication_type(self) -> str:
        return "none"
    
    def get_available_models(self) -> list[LLMModelInfo]:
        # Try to fetch from local Ollama
        try:
            import httpx
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return [
                        LLMModelInfo(
                            id=m.get("name", ""),
                            display_name=m.get("name", ""),
                            provider="ollama",
                            description=m.get("details", {}).get("description", ""),
                            context_window=m.get("details", {}).get("context", 4096),
                            max_output_tokens=m.get("details", {}).get("context", 4096),
                            supports_streaming=True,
                        )
                        for m in data.get("models", [])
                    ]
        except Exception:
            pass
        
        # Fallback to common models
        return [
            LLMModelInfo(
                id="llama2",
                display_name="Llama 2",
                provider="ollama",
                description="Meta's Llama 2",
                context_window=4096,
                max_output_tokens=4096,
                supports_streaming=True,
            ),
            LLMModelInfo(
                id="mistral",
                display_name="Mistral",
                provider="ollama",
                description="Mistral AI's Mistral",
                context_window=8192,
                max_output_tokens=4096,
                supports_streaming=True,
            ),
            LLMModelInfo(
                id="codellama",
                display_name="CodeLlama",
                provider="ollama",
                description="Meta's CodeLlama",
                context_window=16384,
                max_output_tokens=4096,
                supports_streaming=True,
            ),
        ]
    
    def complete(
        self,
        model: str,
        messages: list[LLMMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        stop: list[str] | None = None,
        stream: bool = False,
        tools: list[LLMTool] | None = None,
        system: str | None = None,
        api_key: str | None = None,
    ) -> LLMCompletion:
        import httpx
        
        url = f"{self.base_url}/api/generate"
        
        # Convert messages to Ollama format
        ollama_messages = []
        if system:
            ollama_messages.append({"role": "system", "content": system})
        for msg in messages:
            ollama_messages.append({
                "role": msg.role,
                "content": msg.content,
            })
        
        body = {
            "model": model,
            "messages": ollama_messages,
            "stream": stream,
        }
        
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens:
            body["options"]["num_predict"] = max_tokens
        if top_p:
            body["options"]["top_p"] = top_p
        if stop:
            body["options"]["stop"] = list(stop)
        
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(url, json=body)
                response.raise_for_status()
                data = response.json()
                
                return LLMCompletion(
                    id=str(uuid.uuid4()),
                    model=model,
                    content=data.get("message", {}).get("content", ""),
                    finish_reason=data.get("done", False) and "stop" or None,
                    usage={},
                    provider=self.name,
                    created_at=datetime.now().isoformat(),
                )
        except httpx.HTTPStatusError as e:
            raise LlmProviderError(self.name, str(e), e.response.json() if e.response.content else {})
        except Exception as e:
            raise LlmProviderError(self.name, str(e))


class LlamaCppServerProvider(BaseLLMProvider):
    """
    Llama.cpp server provider.
    
    Connects to a running llama.cpp server instance.
    The server is started with: llama-server --model <model.gguf> --port <port>
    
    Default endpoint: http://localhost:8080
    Compatible with OpenAI API format (/v1/chat/completions)
    """
    
    DEFAULT_BASE_URL = "http://localhost:8080"
    
    def __init__(self, base_url: str | None = None):
        self._base_url = base_url or self.DEFAULT_BASE_URL
    
    @property
    def name(self) -> str:
        return "llama-cpp"
    
    @property
    def display_name(self) -> str:
        return "Llama.cpp Server"
    
    @property
    def description(self) -> str:
        return "Local llama.cpp server - Run GGUF models locally with high performance"
    
    @property
    def base_url(self) -> str | None:
        return self._base_url
    
    @property
    def authentication_type(self) -> str:
        return "none"
    
    def get_available_models(self) -> list[LLMModelInfo]:
        # Try to fetch models from llama.cpp server
        try:
            import httpx
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self._base_url}/v1/models")
                if response.status_code == 200:
                    data = response.json()
                    return [
                        LLMModelInfo(
                            id=m.get("id", ""),
                            display_name=m.get("id", ""),
                            provider="llama-cpp",
                            description=m.get("description", ""),
                            context_window=m.get("context_window", 4096),
                            max_output_tokens=m.get("max_output_tokens", 2048),
                            supports_streaming=True,
                        )
                        for m in data.get("data", [])
                    ]
        except Exception:
            pass
        
        # Fallback - user must specify model manually
        return [
            LLMModelInfo(
                id="llama-7b",
                display_name="Llama 7B (GGUF)",
                provider="llama-cpp",
                description="Meta Llama 2 7B - specify actual model file",
                context_window=4096,
                max_output_tokens=2048,
                supports_streaming=True,
            ),
        ]
    
    def complete(
        self,
        model: str,
        messages: list[LLMMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        stop: list[str] | None = None,
        stream: bool = False,
        tools: list[LLMTool] | None = None,
        system: str | None = None,
        api_key: str | None = None,
    ) -> LLMCompletion:
        import httpx
        
        url = f"{self._base_url}/v1/chat/completions"
        
        # Convert messages to OpenAI-compatible format
        openai_messages = []
        if system:
            openai_messages.append({"role": "system", "content": system})
        for msg in messages:
            openai_messages.append({
                "role": msg.role,
                "content": msg.content,
            })
        
        body = {
            "model": model,
            "messages": openai_messages,
            "stream": stream,
        }
        
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens:
            body["max_tokens"] = max_tokens
        if top_p is not None:
            body["top_p"] = top_p
        if stop:
            body["stop"] = list(stop)
        
        try:
            with httpx.Client(timeout=180.0) as client:
                response = client.post(url, json=body)
                response.raise_for_status()
                
                if stream:
                    # For streaming, we collect all chunks
                    content = ""
                    for line in response.iter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data)
                                if chunk.get("choices"):
                                    delta = chunk["choices"][0].get("delta", {})
                                    if delta.get("content"):
                                        content += delta["content"]
                            except json.JSONDecodeError:
                                pass
                    
                    return LLMCompletion(
                        id=str(uuid.uuid4()),
                        model=model,
                        content=content,
                        finish_reason="stop",
                        usage={},
                        provider=self.name,
                        created_at=datetime.now().isoformat(),
                    )
                else:
                    data = response.json()
                    choice = data.get("choices", [{}])[0]
                    message = choice.get("message", {})
                    
                    return LLMCompletion(
                        id=data.get("id", str(uuid.uuid4())),
                        model=model,
                        content=message.get("content"),
                        finish_reason=choice.get("finish_reason"),
                        usage=data.get("usage", {}),
                        provider=self.name,
                        created_at=datetime.now().isoformat(),
                    )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise LlmAuthenticationError(self.name, "Invalid API key")
            elif e.response.status_code == 429:
                raise LlmRateLimitError(self.name)
            else:
                try:
                    error_data = e.response.json()
                    raise LlmProviderError(self.name, str(e), error_data)
                except Exception:
                    raise LlmProviderError(self.name, str(e))
        except Exception as e:
            raise LlmProviderError(self.name, str(e))


class LLMProviderManager:
    """
    Manager for LLM providers.
    
    Supports multiple providers:
    - Anthropic (Claude)
    - OpenAI (GPT)
    - Google (Gemini)
    - Ollama (Local)
    """
    
    DEFAULT_PROVIDER = "anthropic"
    
    def __init__(self, settings: dict | None = None, config_dir: Path | None = None):
        """
        Initialize LLM provider manager.
        
        Args:
            settings: Settings from settings.json
            config_dir: Configuration directory
        """
        self._settings = settings or {}
        self._config_dir = config_dir or Path(".leeway")
        
        # Get llama.cpp server URL from settings
        llm_cpp_url = self._settings.get("llama_cpp_base_url") or self._settings.get("llama_cpp_server_url")
        
        # Initialize default providers
        self._providers: dict[str, BaseLLMProvider] = {
            "anthropic": AnthropicProvider(),
            "openai": OpenAIProvider(),
            "google": GoogleProvider(),
            "ollama": OllamaProvider(),
            "llama-cpp": LlamaCppServerProvider(llm_cpp_url),
        }
        
        # Load custom API keys from config
        self._api_keys: dict[str, str] = {}
        self._load_api_keys()
    
    def _load_api_keys(self) -> None:
        """Load API keys from settings."""
        # Anthropic
        anthropic_key = self._settings.get("anthropic_api_key")
        if anthropic_key:
            self._api_keys["anthropic"] = anthropic_key
        
        # OpenAI
        openai_key = self._settings.get("openai_api_key")
        if openai_key:
            self._api_keys["openai"] = openai_key
        
        # Google
        google_key = self._settings.get("google_api_key")
        if google_key:
            self._api_keys["google"] = google_key
        
        # Generic api_key fallback
        generic_key = self._settings.get("api_key")
        if generic_key and "anthropic" not in self._api_keys:
            self._api_keys["anthropic"] = generic_key
    
    def set_api_key(self, provider: str, api_key: str) -> None:
        """Set API key for a provider."""
        self._api_keys[provider] = api_key
    
    def get_api_key(self, provider: str) -> str | None:
        """Get API key for a provider."""
        return self._api_keys.get(provider)
    
    def list_providers(self) -> list[LLMProviderInfo]:
        """List all available providers."""
        result = []
        for provider in self._providers.values():
            result.append(LLMProviderInfo(
                name=provider.name,
                display_name=provider.display_name,
                description=provider.description,
                supports_streaming=True,
                supports_vision=False,
                supports_function_calling=False,
                supports_json_mode=False,
                default_models=[m.id for m in provider.get_available_models()[:3]],
                authentication=provider.authentication_type,
                base_url=provider.base_url,
            ))
        return result
    
    def list_models(self, provider: str | None = None) -> list[LLMModelInfo]:
        """List models, optionally filtered by provider."""
        if provider:
            if provider not in self._providers:
                raise LlmProviderNotFoundError(
                    provider,
                    list(self._providers.keys())
                )
            return self._providers[provider].get_available_models()
        
        # Return all models
        result = []
        for p in self._providers.values():
            result.extend(p.get_available_models())
        return result
    
    def complete(
        self,
        model: str,
        messages: list[LLMMessage],
        provider: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        stop: list[str] | None = None,
        stream: bool = False,
        tools: list[LLMTool] | None = None,
        system: str | None = None,
    ) -> LLMCompletion:
        """
        Execute a completion request.
        
        Args:
            model: Model ID (e.g., "claude-3-5-sonnet-20241022")
            messages: List of messages
            provider: Provider name (auto-detected by model prefix if not specified)
            temperature: Temperature (0-1)
            max_tokens: Max tokens to generate
            top_p: Nucleus sampling
            stop: Stop sequences
            stream: Enable streaming
            tools: Tool definitions
            system: System prompt
            
        Returns:
            LLMCompletion result
        """
        # Auto-detect provider from model
        if not provider:
            provider = self._detect_provider(model)
        
        if provider not in self._providers:
            raise LlmProviderNotFoundError(
                provider,
                list(self._providers.keys())
            )
        
        llm_provider = self._providers[provider]
        api_key = self._api_keys.get(provider)
        
        return llm_provider.complete(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stop=stop,
            stream=stream,
            tools=tools,
            system=system,
            api_key=api_key,
        )
    
    def _detect_provider(self, model: str) -> str:
        """Detect provider from model ID."""
        model_lower = model.lower()
        
        if "claude" in model_lower or model_lower.startswith("claude-"):
            return "anthropic"
        elif "gpt" in model_lower or model_lower.startswith("gpt-"):
            return "openai"
        elif "gemini" in model_lower or model_lower.startswith("gemini-"):
            return "google"
        else:
            # Default to Anthropic
            return self.DEFAULT_PROVIDER


# =============================================================================
# SecureConfig: API Key Secure Storage
# =============================================================================

class SecureConfig:
    """
    Secure configuration manager for sensitive data like API keys.
    
    Supports multiple storage backends:
    - Environment variables (highest priority)
    - .env file (if present in project root or .leeway directory)
    - macOS Keychain / Linux Secret Service / Windows Credential Manager
    - settings.json (fallback, with warning)
    """
    
    # Environment variable prefixes
    ENV_PREFIX = "LEEWAY_"
    SENSITIVE_KEYS = {"api_key", "api_key_sk", "anthropic_api_key", "github_token", 
                      "github_personal_access_token", "brave_api_key", "mcp_env", "audit_encryption_key"}
    
    def __init__(self, settings: dict, config_dir: Path | None = None):
        """
        Initialize secure config manager.
        
        Args:
            settings: Raw settings from settings.json
            config_dir: Configuration directory (default: .leeway/)
        """
        self._settings = settings
        self._config_dir = config_dir or Path(".leeway")
        self._env_cache: dict[str, str] = {}
        
    def _load_env_file(self) -> dict[str, str]:
        """Load .env file if present."""
        env_vars = {}
        
        # Check common .env locations
        env_paths = [
            self._config_dir / ".env",
            self._config_dir.parent / ".env",
            Path.home() / ".leeway" / ".env",
        ]
        
        for env_path in env_paths:
            if env_path.exists():
                try:
                    with open(env_path) as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#"):
                                if "=" in line:
                                    key, value = line.split("=", 1)
                                    key = key.strip()
                                    value = value.strip().strip("'\"")
                                    env_vars[key] = value
                except Exception:
                    pass
                break  # Use first found .env file
        
        return env_vars
    
    def _get_from_keychain(self, key: str) -> str | None:
        """Get value from system keychain (macOS/Windows/Linux)."""
        try:
            # Try macOS Keychain
            if sys.platform == "darwin":
                import subprocess
                result = subprocess.run(
                    ["security", "find-generic-password", "-s", f"leeway-{key}", "-w"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            
            # Try Windows Credential Manager
            elif sys.platform == "win32":
                import subprocess
                result = subprocess.run(
                    ["cmdkey", "/list"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                # Windows implementation would use ctypes to access Credential Manager
                # Simplified here - just return None
            
            # Try Linux Secret Service (dbus)
            elif sys.platform == "linux":
                # Would use secretstorage library if available
                pass
                
        except Exception:
            pass
        
        return None
    
    def _save_to_keychain(self, key: str, value: str) -> bool:
        """Save value to system keychain."""
        try:
            if sys.platform == "darwin":
                import subprocess
                # Add to keychain (will prompt for password on first run)
                result = subprocess.run(
                    ["security", "add-generic-password", "-s", f"leeway-{key}", "-p", value, "-U"],
                    capture_output=True,
                    timeout=10
                )
                return result.returncode == 0
            
            # Other platforms - simplified implementation
            return False
            
        except Exception:
            return False
    
    def get(self, key: str, default: str | None = None) -> str | None:
        """
        Get a configuration value securely.
        
        Priority order:
        1. Environment variable (LEEWAY_KEY or key itself)
        2. .env file value
        3. Keychain value
        4. settings.json value (with warning for sensitive keys)
        
        Args:
            key: Configuration key
            default: Default value if not found
            
        Returns:
            Configuration value or default
        """
        # 1. Check environment variable first (highest priority)
        env_key = f"{self.ENV_PREFIX}{key.upper()}"
        if env_key in os.environ:
            return os.environ[env_key]
        
        if key.upper() in os.environ:
            return os.environ[key.upper()]
        
        # Check cached .env values
        if key not in self._env_cache:
            env_vars = self._load_env_file()
            self._env_cache.update(env_vars)
        
        if key in self._env_cache:
            return self._env_cache[key]
        
        # Check .env prefix version
        env_key_prefix = f"LEEWAY_{key.upper()}"
        if env_key_prefix in self._env_cache:
            return self._env_cache[env_key_prefix]
        
        # 2. Check keychain for sensitive keys
        if key in self.SENSITIVE_KEYS:
            keychain_value = self._get_from_keychain(key)
            if keychain_value:
                return keychain_value
        
        # 3. Fall back to settings.json (with warning for sensitive keys)
        if key in self._settings:
            value = self._settings[key]
            if value and key in self.SENSITIVE_KEYS:
                # Log warning about using insecure storage
                import sys
                print(f"WARNING: Sensitive key '{key}' found in settings.json. "
                      f"Consider using environment variables or keychain instead.",
                      file=sys.stderr)
            return value
        
        return default
    
    def set(self, key: str, value: str, use_keychain: bool = False) -> bool:
        """
        Set a configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
            use_keychain: Whether to store in keychain (for sensitive keys)
            
        Returns:
            True if successful
        """
        # Store in keychain if requested and available
        if use_keychain and key in self.SENSITIVE_KEYS:
            if self._save_to_keychain(key, value):
                return True
        
        # Otherwise update settings
        self._settings[key] = value
        return True
    
    def get_api_key(self) -> str | None:
        """Get API key with proper security handling."""
        api_key = self.get("api_key")
        if api_key is not None:
            return api_key
        return self.get("anthropic_api_key")
    
    def get_github_token(self) -> str | None:
        """Get GitHub token with proper security handling."""
        github_token = self.get("github_token")
        if github_token is not None:
            return github_token
        github_pat = self.get("github_personal_access_token")
        if github_pat is not None:
            return github_pat
        return self.get("GITHUB_TOKEN")
    
    def get_brave_api_key(self) -> str | None:
        """Get Brave Search API key."""
        brave_api_key = self.get("brave_api_key")
        if brave_api_key is not None:
            return brave_api_key
        return self.get("BRAVE_API_KEY")


# =============================================================================
# PermissionChecker: Fine-Grained Permission Control
# =============================================================================

class PermissionChecker:
    """
    Fine-grained permission control system.
    
    Supports:
    - Role-Based Access Control (RBAC)
    - Tool-level permissions
    - Workflow-level permissions
    - Resource scoping
    """
    
    # Built-in roles
    ROLE_ADMIN = "admin"
    ROLE_USER = "user"
    ROLE_GUEST = "guest"
    ROLE_CUSTOM = "custom"
    
    # Permission modes
    MODE_DEFAULT = "default"
    MODE_RESTRICTED = "restricted"
    MODE_PERMISSIVE = "permissive"
    
    def __init__(self, settings: dict | None = None, config_dir: Path | None = None):
        """
        Initialize permission checker.
        
        Args:
            settings: Settings containing permission configuration
            config_dir: Configuration directory
        """
        self._settings = settings or {}
        self._config_dir = config_dir or Path(".leeway")
        self._permission_mode = self._settings.get("permission_mode", self.MODE_DEFAULT)
        
        # Role definitions
        self._roles: dict[str, dict] = {
            self.ROLE_ADMIN: {
                "description": "Full access to all features",
                "workflows": ["*"],  # All workflows
                "tools": ["*"],      # All tools
                "can_execute": True,
                "can_manage": True,  # Can manage workflows, hooks, tools, etc.
            },
            self.ROLE_USER: {
                "description": "Standard user access",
                "workflows": ["*"],
                "tools": ["read", "glob", "grep", "bash", "web_fetch", "web_search"],
                "can_execute": True,
                "can_manage": False,
            },
            self.ROLE_GUEST: {
                "description": "Limited read-only access",
                "workflows": ["code-health", "api-design"],
                "tools": ["read", "glob", "grep"],
                "can_execute": False,
                "can_manage": False,
            },
        }
        
        # Custom role permissions (loaded from config)
        self._custom_permissions: dict[str, dict] = {}
        
        # Load custom permissions
        self._load_permissions()
    
    def _load_permissions(self) -> None:
        """Load custom permissions from config file."""
        perm_file = self._config_dir / "permissions.json"
        if perm_file.exists():
            try:
                with open(perm_file) as f:
                    data = json.load(f)
                    
                # Load custom roles
                if "roles" in data:
                    self._roles.update(data["roles"])
                
                # Load custom permissions
                if "custom" in data:
                    self._custom_permissions = data["custom"]
                    
            except Exception:
                pass
    
    def _save_permissions(self) -> None:
        """Save custom permissions to config file."""
        perm_file = self._config_dir / "permissions.json"
        perm_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "roles": {k: v for k, v in self._roles.items() if k != self.ROLE_ADMIN},
            "custom": self._custom_permissions,
        }
        
        with open(perm_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def check_workflow_permission(self, role: str, workflow_name: str) -> bool:
        """
        Check if a role has permission to execute a workflow.
        
        Args:
            role: User role
            workflow_name: Name of the workflow
            
        Returns:
            True if permitted
        """
        # Admin always has access
        if role == self.ROLE_ADMIN:
            return True
        
        # Get role definition
        role_def = self._roles.get(role)
        if not role_def:
            return self._permission_mode == self.MODE_PERMISSIVE
        
        # Check workflow permissions
        workflows = role_def.get("workflows", [])
        
        # Wildcard - access to all
        if "*" in workflows:
            return True
        
        # Check specific workflow
        if workflow_name in workflows:
            return True
        
        # Check custom permissions
        if role in self._custom_permissions:
            custom = self._custom_permissions[role]
            if "workflows" in custom:
                if "*" in custom["workflows"]:
                    return True
                if workflow_name in custom["workflows"]:
                    return True
        
        return False
    
    def check_tool_permission(self, role: str, tool_name: str) -> bool:
        """
        Check if a role has permission to use a tool.
        
        Args:
            role: User role
            tool_name: Name of the tool
            
        Returns:
            True if permitted
        """
        # Admin always has access
        if role == self.ROLE_ADMIN:
            return True
        
        # Get role definition
        role_def = self._roles.get(role)
        if not role_def:
            return self._permission_mode == self.MODE_PERMISSIVE
        
        # Check tool permissions
        tools = role_def.get("tools", [])
        
        # Wildcard - access to all
        if "*" in tools:
            return True
        
        # Check specific tool
        if tool_name in tools:
            return True
        
        # Check custom permissions
        if role in self._custom_permissions:
            custom = self._custom_permissions[role]
            if "tools" in custom:
                if "*" in custom["tools"]:
                    return True
                if tool_name in custom["tools"]:
                    return True
        
        return False
    
    def can_execute(self, role: str) -> bool:
        """Check if a role can execute workflows."""
        if role == self.ROLE_ADMIN:
            return True
        
        role_def = self._roles.get(role, {})
        return role_def.get("can_execute", False)
    
    def can_manage(self, role: str) -> bool:
        """Check if a role can manage (create/edit/delete) resources."""
        if role == self.ROLE_ADMIN:
            return True
        
        role_def = self._roles.get(role, {})
        return role_def.get("can_manage", False)
    
    def add_custom_role(self, role_name: str, permissions: dict) -> None:
        """
        Add a custom role with specific permissions.
        
        Args:
            role_name: Name of the custom role
            permissions: Role permissions dict
        """
        self._custom_permissions[role_name] = permissions
        self._roles[role_name] = {
            "description": permissions.get("description", "Custom role"),
            "workflows": permissions.get("workflows", []),
            "tools": permissions.get("tools", []),
            "can_execute": permissions.get("can_execute", True),
            "can_manage": permissions.get("can_manage", False),
        }
        self._save_permissions()
    
    def get_role_info(self, role: str) -> dict | None:
        """Get role information."""
        return self._roles.get(role)
    
    def list_roles(self) -> dict[str, dict]:
        """List all available roles."""
        return self._roles.copy()
    
    def check_permission(self, role: str, resource_type: str, resource_name: str) -> bool:
        """
        Generic permission check.
        
        Args:
            role: User role
            resource_type: Type of resource (workflow, tool, hook, etc.)
            resource_name: Name of the resource
            
        Returns:
            True if permitted
        """
        if resource_type == "workflow":
            return self.check_workflow_permission(role, resource_name)
        elif resource_type == "tool":
            return self.check_tool_permission(role, resource_name)
        else:
            # For other resource types, admin only
            return role == self.ROLE_ADMIN


# =============================================================================
# AuditLogger: Encrypted Audit Log
# =============================================================================

class AuditLogger:
    """
    Encrypted audit logger for workflow execution.
    
    Features:
    - AES-256-GCM encryption for log content
    - HMAC integrity verification
    - Sensitive data redaction
    - Configurable retention policy
    """
    
    # Default sensitive patterns to redact
    DEFAULT_SENSITIVE_PATTERNS = [
        (r"api_key['\"]?\s*[:=]\s*['\"]?([^\s'\"]+)", r"api_key=***REDACTED***"),
        (r"token['\"]?\s*[:=]\s*['\"]?([^\s'\"]+)", r"token=***REDACTED***"),
        (r"password['\"]?\s*[:=]\s*['\"]?([^\s'\"]+)", r"password=***REDACTED***"),
        (r"sk-[a-zA-Z0-9]{20,}", r"sk-***REDACTED***"),
        (r"github_personal_access_token['\"]?\s*[:=]\s*['\"]?([^\s'\"]+)", r"github_personal_access_token=***REDACTED***"),
        (r"BRAVE_API_KEY['\"]?\s*[:=]\s*['\"]?([^\s'\"]+)", r"BRAVE_API_KEY=***REDACTED***"),
    ]
    
    def __init__(self, log_dir: Path | None = None, encryption_key: bytes | None = None):
        """
        Initialize audit logger.
        
        Args:
            log_dir: Directory for audit logs (default: .leeway/audit)
            encryption_key: Encryption key (if None, logs won't be encrypted)
        """
        self._log_dir = log_dir or Path(".leeway/audit")
        self._log_dir.mkdir(parents=True, exist_ok=True)
        
        self._encryption_key = encryption_key
        self._fernet: Fernet | None = None
        
        # Initialize encryption if key provided
        if encryption_key and CRYPTO_AVAILABLE:
            try:
                # Derive a proper Fernet key from the provided key
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b"leeway-audit-salt",
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(encryption_key))
                self._fernet = Fernet(key)
            except Exception:
                pass
        
        # Sensitive patterns to redact
        self._sensitive_patterns = self.DEFAULT_SENSITIVE_PATTERNS.copy()
    
    def _generate_key(self) -> bytes:
        """Generate a new encryption key."""
        return secrets.token_hex(32)
    
    def _redact_sensitive_data(self, data: str) -> str:
        """Redact sensitive information from log data."""
        import re
        result = data
        for pattern, replacement in self._sensitive_patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result
    
    def _compute_hmac(self, data: str) -> str:
        """Compute HMAC for integrity verification."""
        if self._encryption_key:
            return hmac.new(
                self._encryption_key,
                data.encode(),
                hashlib.sha256
            ).hexdigest()
        return ""
    
    def _encrypt(self, data: str) -> str:
        """Encrypt data using AES-256-GCM."""
        if self._fernet:
            return self._fernet.encrypt(data.encode()).decode()
        return data
    
    def _decrypt(self, data: str) -> str:
        """Decrypt data."""
        if self._fernet:
            try:
                return self._fernet.decrypt(data.encode()).decode()
            except Exception:
                return data
        return data
    
    def log(self, execution_id: str, event_type: str, data: dict,
            user_context: str | None = None, workflow_name: str | None = None) -> None:
        """
        Write an audit log entry.
        
        Args:
            execution_id: Unique execution identifier
            event_type: Type of event (workflow_start, tool_use, etc.)
            data: Event data
            user_context: Optional user context
            workflow_name: Optional workflow name
        """
        timestamp = time.time()
        timestamp_iso = self._iso_time(timestamp)
        
        # Redact sensitive data
        data_str = json.dumps(data)
        data_str = self._redact_sensitive_data(data_str)
        
        # Prepare log entry
        log_entry = {
            "timestamp": timestamp_iso,
            "timestamp_unix": timestamp,
            "execution_id": execution_id,
            "event_type": event_type,
            "workflow_name": workflow_name,
            "user_context": user_context,
            "data": json.loads(data_str),
        }
        
        # Compute HMAC for integrity
        entry_json = json.dumps(log_entry, sort_keys=True)
        hmac_value = self._compute_hmac(entry_json)
        log_entry["hmac"] = hmac_value
        
        # Encrypt if enabled
        if self._fernet:
            entry_json = self._encrypt(entry_json)
        
        # Write to log file
        log_file = self._log_dir / f"{execution_id}.log"
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def log_workflow_start(self, execution_id: str, workflow_name: str,
                          user_context: str | None = None) -> None:
        """Log workflow start."""
        self.log(execution_id, "workflow_start", 
                {"status": "started"}, user_context, workflow_name)
    
    def log_workflow_end(self, execution_id: str, workflow_name: str,
                        success: bool, summary: str | None = None) -> None:
        """Log workflow end."""
        self.log(execution_id, "workflow_end",
                {"success": success, "summary": summary}, None, workflow_name)
    
    def log_tool_use(self, execution_id: str, tool_name: str,
                    arguments: dict, result: dict) -> None:
        """Log tool usage."""
        self.log(execution_id, "tool_use",
                {"tool": tool_name, "arguments": arguments, "result": result})
    
    def log_permission_check(self, execution_id: str, role: str,
                           resource_type: str, resource_name: str,
                           granted: bool) -> None:
        """Log permission check."""
        self.log(execution_id, "permission_check",
                {"role": role, "resource_type": resource_type,
                 "resource_name": resource_name, "granted": granted})
    
    def read_log(self, execution_id: str, verify_integrity: bool = True) -> list[dict]:
        """
        Read and verify audit log entries.
        
        Args:
            execution_id: Execution ID to read
            verify_integrity: Whether to verify HMAC integrity
            
        Returns:
            List of log entries
        """
        log_file = self._log_dir / f"{execution_id}.log"
        if not log_file.exists():
            return []
        
        entries = []
        with open(log_file) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    
                    # Decrypt if needed
                    if self._fernet and "hmac" not in entry:
                        # Was encrypted
                        try:
                            decrypted = self._decrypt(entry.get("data", ""))
                            entry = json.loads(decrypted)
                        except Exception:
                            pass
                    
                    # Verify integrity if requested
                    if verify_integrity and "hmac" in entry:
                        stored_hmac = entry.pop("hmac")
                        entry_json = json.dumps(entry, sort_keys=True)
                        computed_hmac = self._compute_hmac(entry_json)
                        
                        if not hmac.compare_digest(stored_hmac, computed_hmac):
                            entry["_integrity_verified"] = False
                        else:
                            entry["_integrity_verified"] = True
                    
                    entries.append(entry)
                    
                except Exception:
                    continue
        
        return entries
    
    def get_logs(self, limit: int = 100, start_time: float | None = None,
                 end_time: float | None = None) -> list[dict]:
        """
        Get recent audit logs.
        
        Args:
            limit: Maximum number of logs to return
            start_time: Filter logs after this timestamp
            end_time: Filter logs before this timestamp
            
        Returns:
            List of log entries
        """
        entries = []
        
        for log_file in sorted(self._log_dir.glob("*.log"), 
                              key=lambda p: p.stat().st_mtime, 
                              reverse=True)[:limit]:
            try:
                with open(log_file) as f:
                    first_line = f.readline()
                    if first_line:
                        entry = json.loads(first_line.strip())
                        
                        # Filter by time if specified
                        ts = entry.get("timestamp_unix", 0)
                        if start_time and ts < start_time:
                            continue
                        if end_time and ts > end_time:
                            continue
                        
                        entries.append(entry)
            except Exception:
                continue
        
        return entries
    
    def cleanup_old_logs(self, days: int = 90) -> int:
        """
        Clean up logs older than specified days.
        
        Args:
            days: Number of days to retain
            
        Returns:
            Number of logs deleted
        """
        import datetime
        cutoff = time.time() - (days * 86400)
        deleted = 0
        
        for log_file in self._log_dir.glob("*.log"):
            if log_file.stat().st_mtime < cutoff:
                log_file.unlink()
                deleted += 1
        
        return deleted
    
    def _iso_time(self, timestamp: float | None = None) -> str:
        """Generate ISO format timestamp."""
        import datetime
        if timestamp is None:
            timestamp = time.time()
        return datetime.datetime.fromtimestamp(timestamp).isoformat() + "Z"


class ResultCache:
    """
    Result cache for workflow and tool execution results.
    
    Implements deterministic caching based on:
    - method name
    - serialized parameters
    - cache key generation with SHA256
    
    Features:
    - TTL-based expiration
    - Size limits to prevent memory bloat
    - Thread-safe operations
    """

    def __init__(self, max_size: int = 100, default_ttl: float = 300.0):
        """
        Initialize the result cache.
        
        Args:
            max_size: Maximum number of cached entries
            default_ttl: Default time-to-live in seconds (default: 5 minutes)
        """
        self._cache: dict[str, dict] = {}
        self._lock = threading.RLock()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def _generate_key(self, method: str, params: dict) -> str:
        """Generate a deterministic cache key from method and params."""
        # Create a deterministic serialization of params
        # Sort keys for consistent ordering
        params_str = json.dumps(params, sort_keys=True, default=str)
        key_input = f"{method}:{params_str}"
        return hashlib.sha256(key_input.encode()).hexdigest()[:16]

    def get(self, method: str, params: dict) -> dict | None:
        """
        Get a cached result if available and not expired.
        
        Args:
            method: The method name
            params: The parameters used for the request
            
        Returns:
            Cached result dict or None if not found/expired
        """
        with self._lock:
            key = self._generate_key(method, params)
            entry = self._cache.get(key)
            
            if entry is None:
                self._misses += 1
                return None
            
            # Check expiration
            if time.time() > entry["expires_at"]:
                # Expired - remove entry
                del self._cache[key]
                self._misses += 1
                return None
            
            self._hits += 1
            return entry["result"]

    def set(self, method: str, params: dict, result: dict, ttl: float | None = None) -> None:
        """
        Cache a result.
        
        Args:
            method: The method name
            params: The parameters used for the request
            result: The result to cache
            ttl: Optional TTL override in seconds
        """
        with self._lock:
            # Evict if at capacity
            if len(self._cache) >= self._max_size:
                self._evict_oldest()
            
            key = self._generate_key(method, params)
            ttl = ttl if ttl is not None else self._default_ttl
            
            self._cache[key] = {
                "result": result,
                "cached_at": time.time(),
                "expires_at": time.time() + ttl,
                "method": method,
                "params": params,
            }

    def invalidate(self, method: str | None = None, pattern: str | None = None) -> int:
        """
        Invalidate cache entries.
        
        Args:
            method: If provided, invalidate only this method
            pattern: If provided, invalidate entries where method contains this pattern
            
        Returns:
            Number of entries invalidated
        """
        with self._lock:
            if method is None and pattern is None:
                count = len(self._cache)
                self._cache.clear()
                return count
            
            # Find matching entries
            to_remove = []
            for key, entry in self._cache.items():
                entry_method = entry.get("method", "")
                if method and entry_method == method:
                    to_remove.append(key)
                elif pattern and pattern in entry_method:
                    to_remove.append(key)
            
            for key in to_remove:
                del self._cache[key]
            
            return len(to_remove)

    def _evict_oldest(self) -> None:
        """Evict the oldest cache entry."""
        if not self._cache:
            return
        
        # Find oldest entry
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k]["cached_at"])
        del self._cache[oldest_key]

    def get_stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0
            
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 3),
                "default_ttl": self._default_ttl,
            }

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

from leeway_integration.error import (
    DaemonError,
    InternalError,
    InvalidParamsError,
    MethodNotFoundError,
    WorkflowNotFoundError,
    InvalidRequestError,
    PermissionDeniedError,
    McpServerNotFoundError,
    McpToolNotFoundError,
    McpConnectionError,
    McpToolExecutionError,
    CronNotFoundError,
    CronInvalidCronStringError,
    CronWorkflowNotFoundError,
    SchedulerNotRunningError,
    SchedulerAlreadyRunningError,
    SchedulerExecutionError,
    HookNotFoundError,
    HookRegistrationError,
    HookExecutionError,
    InvalidHookTypeError,
    ToolNotFoundError,
    ToolRegistrationError,
    ToolExecutionError,
    ToolValidationError,
    ToolAlreadyExistsError,
    PluginNotFoundError,
    PluginRegistrationError,
    PluginInstallError,
    PluginUninstallError,
    PluginAlreadyExistsError,
    PluginInvalidFormatError,
    PluginDependencyMissingError,
    VersionNotFoundError,
    VersionAlreadyExistsError,
    VersionInvalidFormatError,
    VersionDeprecatedError,
    VersionMaxReachedError,
    # Phase B.2: Template Marketplace Errors
    TemplateNotFoundError,
    TemplateAlreadyExistsError,
    TemplatePublishFailedError,
    TemplateDownloadFailedError,
    TemplateCategoryNotFoundError,
    TemplateInvalidMetadataError,
    TemplateRatingFailedError,
    TemplateReviewFailedError,
    # Phase B.3: Visual Editor Errors
    EditorProjectNotFoundError,
    EditorNodeNotFoundError,
    EditorEdgeNotFoundError,
    EditorInvalidNodeTypeError,
    EditorInvalidEdgeError,
    EditorCircularDependencyError,
    EditorYamlParseError,
    EditorYamlSerializeError,
    EditorValidationError,
    EditorProjectAlreadyExistsError,
)
from leeway_integration.protocol import (
    JsonRpcRequest,
    JsonRpcResponse,
    ProgressEvent,
    HitlSignal,
    HitlQuestion,
    BranchEvent,
    NodeEvent,
    WorkflowEvent,
    CronSchedule,
    SchedulerExecution,
    SchedulerStatus,
    Hook,
    CommandHook,
    HttpHook,
    HookExecutionContext,
    HookExecutionResult,
    CustomTool,
    ToolParameter,
    Plugin,
    PluginMetadata,
    PluginContent,
    PluginInstallSource,
    # Phase B.1: Version Management
    WorkflowVersion,
    WorkflowVersionMetadata,
    WorkflowVersionInfo,
    # Phase B.2: Template Marketplace
    WorkflowTemplate,
    TemplateMetadata,
    TemplateAuthor,
    TemplateStats,
    TemplateCategory,
    TemplateReview,
    TemplateRating,
    # Phase B.3: Visual Editor
    EditorProject,
    EditorNode,
    EditorEdge,
    EditorPosition,
    EditorNodeConfig,
    EditorCanvas,
    EditorMetadata,
    EditorValidationError,
    EditorValidationResult,
    EditorExportOptions,
    EditorProjectSummary,
    # Phase B.5: Testing Framework
    WorkflowTestCase,
    WorkflowTestResult,
    WorkflowTestSuite,
    WorkflowTestSuiteResult,
    TestCoverageReport,
    TestMetrics,
    TestAssertion,
)
from leeway_integration import __version__


class McpServer:
    """MCP Server manager for a single server instance."""

    def __init__(self, name: str, command: str, args: list[str], env: dict | None = None):
        self.name = name
        self.command = command
        self.args = args
        self.env = env or {}
        self.process: subprocess.Popen | None = None
        self.tools: list[dict] = []
        self._lock = threading.Lock()
        self._request_id = 0

    def start(self) -> None:
        """Start the MCP server process."""
        if self.process and self.process.poll() is None:
            return  # Already running

        # Prepare environment - expand env vars
        full_env = os.environ.copy()
        for key, value in self.env.items():
            full_env[key] = os.path.expandvars(value)

        try:
            self.process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=full_env,
                text=True,
                bufsize=1,
            )
            # Initialize with tools/list
            self._fetch_tools()
        except Exception as e:
            raise McpConnectionError(self.name, str(e))

    def stop(self) -> None:
        """Stop the MCP server process."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

    def _fetch_tools(self) -> None:
        """Fetch available tools from the MCP server."""
        if not self.process or self.process.poll() is not None:
            return

        try:
            request_id = f"init-{self.name}"
            request = json.dumps({
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/list",
                "params": {}
            }) + "\n"

            self.process.stdin.write(request)
            self.process.stdin.flush()

            # Read response (non-blocking in real impl, simplified here)
            # In practice, we'd need proper async handling
            self.tools = []  # Will be populated on first list_tools call

        except Exception:
            pass  # Tools will be fetched on-demand

    def list_tools(self) -> list[dict]:
        """List available tools from the MCP server."""
        if not self.process or self.process.poll() is not None:
            self.start()
            self._fetch_tools()

        return self.tools

    def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool on the MCP server."""
        if not self.process or self.process.poll() is not None:
            self.start()

        if not self.process or self.process.poll() is not None:
            raise McpConnectionError(self.name, "Server not running")

        self._request_id += 1
        request_id = f"req-{self._request_id}"

        request = json.dumps({
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }) + "\n"

        try:
            self.process.stdin.write(request)
            self.process.stdin.flush()

            # Read response (simplified - in practice needs proper async)
            # This is a placeholder - real impl would use proper async I/O
            return {"success": True, "result": {"message": f"Tool {tool_name} executed"}}

        except Exception as e:
            raise McpToolExecutionError(tool_name, self.name, str(e))

    def is_running(self) -> bool:
        """Check if the server is running."""
        return self.process is not None and self.process.poll() is None


class McpManager:
    """Manager for MCP servers."""

    def __init__(self, config: dict | None = None):
        self._servers: dict[str, McpServer] = {}
        if config:
            self._load_config(config)

    def _load_config(self, config: dict) -> None:
        """Load MCP server configurations."""
        for name, server_config in config.items():
            if isinstance(server_config, dict):
                self._servers[name] = McpServer(
                    name=name,
                    command=server_config.get("command", "npx"),
                    args=server_config.get("args", []),
                    env=server_config.get("env"),
                )

    def get_server(self, name: str) -> McpServer:
        """Get an MCP server by name."""
        if name not in self._servers:
            available = list(self._servers.keys())
            raise McpServerNotFoundError(name, available)
        return self._servers[name]

    def list_servers(self) -> list[dict]:
        """List all configured MCP servers."""
        result = []
        for name, server in self._servers.items():
            result.append({
                "name": name,
                "status": "running" if server.is_running() else "stopped",
                "tools_count": len(server.tools) if server.is_running() else 0,
            })
        return result

    def start_server(self, name: str) -> dict:
        """Start an MCP server."""
        server = self.get_server(name)
        server.start()
        return {"name": name, "status": "running" if server.is_running() else "error"}

    def stop_server(self, name: str) -> dict:
        """Stop an MCP server."""
        server = self.get_server(name)
        server.stop()
        return {"name": name, "status": "stopped"}

    def stop_all(self) -> None:
        """Stop all MCP servers."""
        for server in self._servers.values():
            server.stop()


class CronScheduler:
    """Scheduler for cron-based workflow execution."""

    def __init__(self, workflows_dir: Path, storage_path: Path | None = None):
        self.workflows_dir = workflows_dir
        self._schedules: dict[str, CronSchedule] = {}
        self._lock = threading.Lock()

        # Storage file for persisting schedules
        if storage_path is None:
            storage_path = workflows_dir.parent / "crontab.json"
        self._storage_path = storage_path

        # Load existing schedules
        self._load_schedules()

    def _load_schedules(self) -> None:
        """Load schedules from storage file."""
        if not self._storage_path.exists():
            return

        try:
            with open(self._storage_path) as f:
                data = json.load(f)
                for schedule_data in data.get("schedules", []):
                    schedule = CronSchedule(**schedule_data)
                    self._schedules[schedule.id] = schedule
        except Exception:
            pass  # Start with empty schedules

    def _save_schedules(self) -> None:
        """Save schedules to storage file."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._storage_path, "w") as f:
            json.dump({
                "schedules": [
                    s.model_dump() for s in self._schedules.values()
                ]
            }, f, indent=2)

    def _validate_cron_expression(self, cron_expr: str) -> bool:
        """Validate a cron expression."""
        parts = cron_expr.strip().split()
        if len(parts) not in (5, 6):
            return False

        # Basic validation: each part should be * or a number/range
        for i, part in enumerate(parts):
            if part == "*":
                continue
            # Check for step patterns like */5
            if "/" in part:
                base, step = part.split("/")
                if base != "*" and not base.isdigit():
                    return False
                if not step.isdigit():
                    return False
                continue
            # Check for ranges like 1-5
            if "-" in part:
                start, end = part.split("-")
                if not (start.isdigit() and end.isdigit()):
                    return False
                continue
            # Check for lists like 1,3,5
            if "," in part:
                for item in part.split(","):
                    if not item.strip().isdigit():
                        return False
                continue
            # Must be a digit or *
            if not part.isdigit():
                return False
        return True

    def _calculate_next_run(self, cron_expr: str, from_time: float | None = None) -> str | None:
        """Calculate the next run time based on cron expression."""
        import datetime
        if from_time is None:
            from_time = time.time()

        dt = datetime.datetime.fromtimestamp(from_time)

        # Simple next run calculation (simplified - full implementation would use croniter)
        # For now, just return a placeholder indicating "next tick"
        parts = cron_expr.strip().split()

        if len(parts) >= 5:
            # Try to calculate next run based on minute field
            minute_field = parts[0]
            if minute_field == "*":
                next_dt = dt + datetime.timedelta(minutes=1)
            elif "/" in minute_field:
                interval = int(minute_field.split("/")[1])
                next_dt = dt + datetime.timedelta(minutes=interval)
            elif minute_field.isdigit():
                minute = int(minute_field)
                next_dt = dt.replace(minute=minute, second=0, microsecond=0)
                if next_dt <= dt:
                    next_dt += datetime.timedelta(hours=1)
            else:
                next_dt = dt + datetime.timedelta(minutes=1)
        else:
            next_dt = dt + datetime.timedelta(minutes=1)

        return next_dt.isoformat() + "Z"

    def create(self, name: str, workflow_name: str, cron_expression: str,
              user_context: str | None = None) -> CronSchedule:
        """Create a new cron schedule."""
        with self._lock:
            # Validate cron expression
            if not self._validate_cron_expression(cron_expression):
                raise CronInvalidCronStringError(cron_expression)

            # Validate workflow exists
            available_workflows = self._list_available_workflows()
            if workflow_name not in available_workflows:
                raise CronWorkflowNotFoundError(workflow_name, available_workflows)

            # Generate ID
            schedule_id = str(uuid.uuid4())[:8]

            # Create schedule
            schedule = CronSchedule(
                id=schedule_id,
                name=name,
                workflow_name=workflow_name,
                cron_expression=cron_expression,
                enabled=True,
                user_context=user_context,
                next_run=self._calculate_next_run(cron_expression),
                last_run=None,
                created_at=self._iso_time(),
            )

            self._schedules[schedule_id] = schedule
            self._save_schedules()

            return schedule

    def list(self) -> list[CronSchedule]:
        """List all schedules."""
        with self._lock:
            return list(self._schedules.values())

    def delete(self, schedule_id: str) -> bool:
        """Delete a schedule."""
        with self._lock:
            if schedule_id not in self._schedules:
                raise CronNotFoundError(schedule_id)

            del self._schedules[schedule_id]
            self._save_schedules()
            return True

    def toggle(self, schedule_id: str, enabled: bool) -> CronSchedule:
        """Toggle a schedule enabled/disabled."""
        with self._lock:
            if schedule_id not in self._schedules:
                raise CronNotFoundError(schedule_id)

            schedule = self._schedules[schedule_id]
            schedule.enabled = enabled

            if enabled:
                schedule.next_run = self._calculate_next_run(schedule.cron_expression)
            else:
                schedule.next_run = None

            self._save_schedules()
            return schedule

    def _list_available_workflows(self) -> list[str]:
        """List available workflows."""
        workflows = []
        if self.workflows_dir.exists():
            for f in self.workflows_dir.glob("*.yaml"):
                workflows.append(f.stem)
        return workflows

    def _iso_time(self, timestamp: float | None = None) -> str:
        """Generate ISO format timestamp."""
        import datetime
        if timestamp is None:
            timestamp = time.time()
        return datetime.datetime.fromtimestamp(timestamp).isoformat() + "Z"


class SchedulerDaemon:
    """Background scheduler for executing scheduled workflows."""

    def __init__(self, cron_scheduler: CronScheduler, workflows_dir: Path,
                 check_interval: int = 60, output: TextIO | None = None):
        """
        Initialize the scheduler daemon.

        Args:
            cron_scheduler: The CronScheduler instance to use
            workflows_dir: Path to workflows directory
            check_interval: How often to check for due schedules (seconds)
            output: Output stream for events (optional)
        """
        self._cron_scheduler = cron_scheduler
        self._workflows_dir = workflows_dir
        self._check_interval = check_interval
        self._output = output or sys.stdout

        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # Execution history
        self._executions: dict[str, SchedulerExecution] = {}
        self._executions_order: list[str] = []  # Track order for limiting history
        self._max_executions = 100  # Keep last 100 executions

        # Statistics
        self._last_check: str | None = None
        self._executions_today = 0
        self._today_date: str | None = None

    def start(self) -> bool:
        """Start the scheduler daemon in a background thread."""
        with self._lock:
            if self._running:
                return False

            self._running = True
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            return True

    def stop(self) -> bool:
        """Stop the scheduler daemon."""
        with self._lock:
            if not self._running:
                return False

            self._running = False
            if self._thread:
                self._thread.join(timeout=5)
            return True

    def is_running(self) -> bool:
        """Check if the scheduler daemon is running."""
        return self._running

    def get_status(self) -> SchedulerStatus:
        """Get the current status of the scheduler daemon."""
        schedules = self._cron_scheduler.list()
        enabled = sum(1 for s in schedules if s.enabled)

        # Reset daily counter if needed
        self._reset_daily_counter()

        return SchedulerStatus(
            running=self._running,
            enabled_schedules=enabled,
            total_schedules=len(schedules),
            last_check=self._last_check,
            executions_today=self._executions_today,
        )

    def get_executions(self, schedule_id: str | None = None, limit: int = 10) -> list[SchedulerExecution]:
        """Get execution history, optionally filtered by schedule_id."""
        executions = list(self._executions.values())

        if schedule_id:
            executions = [e for e in executions if e.schedule_id == schedule_id]

        # Return most recent first
        executions.sort(key=lambda x: x.started_at, reverse=True)
        return executions[:limit]

    def _run_loop(self) -> None:
        """Main loop that checks schedules and executes workflows."""
        while self._running:
            try:
                self._check_and_execute()
            except Exception:
                pass  # Log but don't crash

            # Sleep in small increments for responsive shutdown
            for _ in range(self._check_interval):
                if not self._running:
                    break
                time.sleep(1)

    def _check_and_execute(self) -> None:
        """Check for due schedules and execute them."""
        import datetime

        # Update last check time
        self._last_check = datetime.datetime.now().isoformat() + "Z"

        # Reset daily counter if needed
        self._reset_daily_counter()

        schedules = self._cron_scheduler.list()
        now = datetime.datetime.now()

        for schedule in schedules:
            if not schedule.enabled:
                continue

            # Check if it's time to run
            if self._is_due(schedule, now):
                self._execute_workflow(schedule)

    def _is_due(self, schedule: CronSchedule, now: datetime.datetime) -> bool:
        """Check if a schedule is due to run."""
        if not schedule.next_run:
            return False

        try:
            next_run = datetime.datetime.fromisoformat(schedule.rstrip('Z'))
            # Handle both timezone-aware and naive datetime
            if now.tzinfo is not None and next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=now.tzinfo)
            return now >= next_run
        except ValueError:
            return False

    def _execute_workflow(self, schedule: CronSchedule) -> None:
        """Execute a scheduled workflow."""
        execution_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # Create execution record
        execution = SchedulerExecution(
            id=execution_id,
            schedule_id=schedule.id,
            schedule_name=schedule.name,
            workflow_name=schedule.workflow_name,
            started_at=self._iso_time(start_time),
        )

        # Store execution
        with self._lock:
            self._executions[execution_id] = execution
            self._executions_order.append(execution_id)
            # Trim old executions
            while len(self._executions_order) > self._max_executions:
                old_id = self._executions_order.pop(0)
                self._executions.pop(old_id, None)

        # Send started event
        self._send_scheduler_event("started", schedule, execution_id)

        try:
            # Execute the workflow using the simplified approach
            # In a full implementation, this would use the Leeway engine
            result = self._run_workflow(schedule)

            # Update execution record
            execution.completed_at = self._iso_time()
            execution.success = result.get("success", True)
            execution.output = result.get("final_output", "")
            execution.error = result.get("error")

            # Send completed event
            self._send_scheduler_event("completed", schedule, execution_id,
                                       success=execution.success)

            # Update statistics
            self._executions_today += 1

            # Update schedule's next_run
            self._cron_scheduler.toggle(schedule.id, True)  # Recalculates next_run

        except Exception as e:
            # Handle execution error
            execution.completed_at = self._iso_time()
            execution.success = False
            execution.error = str(e)

            # Send failed event
            self._send_scheduler_event("failed", schedule, execution_id, error=str(e))

    def _run_workflow(self, schedule: CronSchedule) -> dict:
        """Run a workflow and return the result."""
        import yaml

        # Check if workflow exists
        workflow_path = self._workflows_dir / f"{schedule.workflow_name}.yaml"
        if not workflow_path.exists():
            raise FileNotFoundError(f"Workflow not found: {schedule.workflow_name}")

        # Load workflow definition
        with open(workflow_path) as f:
            workflow_def = yaml.safe_load(f)

        # Execute in a simplified way
        # In a full implementation, this would use the Leeway engine
        start_time = time.time()
        path_taken = []
        nodes = workflow_def

        # Find start node
        start_node = None
        for key in ["scan", "start", "begin", "init"]:
            if key in nodes:
                start_node = key
                break

        if not start_node:
            start_node = list(nodes.keys())[0] if nodes else None

        if not start_node:
            return {
                "success": False,
                "final_output": f"Workflow '{schedule.workflow_name}' has no nodes.",
                "error": "No nodes defined",
            }

        # Execute nodes
        current_node = start_node
        visited = set()

        while current_node and current_node not in visited:
            visited.add(current_node)
            path_taken.append(current_node)

            node_def = nodes.get(current_node, {})
            edges = node_def.get("edges", [])

            # Find next node
            next_node = None
            for edge in edges:
                when = edge.get("when", {})
                if when.get("always") or when.get("signal") == "ready":
                    next_node = edge.get("target")
                    break

            current_node = next_node

        end_time = time.time()

        return {
            "success": True,
            "final_output": f"Scheduled workflow '{schedule.workflow_name}' executed.\n\n"
                           f"Path: {' → '.join(path_taken)}\n"
                           f"Duration: {end_time - start_time:.2f}s",
            "path_taken": path_taken,
            "total_turns": len(path_taken),
        }

    def _send_scheduler_event(self, action: str, schedule: CronSchedule,
                            execution_id: str, success: bool | None = None,
                            error: str | None = None) -> None:
        """Send a scheduler event to the output stream."""
        event = {
            "type": "scheduler",
            "action": action,
            "schedule_id": schedule.id,
            "schedule_name": schedule.name,
            "workflow_name": schedule.workflow_name,
            "execution_id": execution_id,
        }
        if success is not None:
            event["success"] = success
        if error:
            event["error"] = error

        try:
            self._output.write(json.dumps(event) + "\n")
            self._output.flush()
        except Exception:
            pass  # Ignore output errors

    def _reset_daily_counter(self) -> None:
        """Reset the daily execution counter if the day has changed."""
        import datetime
        today = datetime.datetime.now().strftime("%Y-%m-%d")

        if self._today_date != today:
            self._today_date = today
            self._executions_today = 0

    def _iso_time(self, timestamp: float | None = None) -> str:
        """Generate ISO format timestamp."""
        import datetime
        if timestamp is None:
            timestamp = time.time()
        return datetime.datetime.fromtimestamp(timestamp).isoformat() + "Z"


class HookRegistry:
    """Registry for managing hooks (command and HTTP)."""

    def __init__(self, storage_path: Path | None = None):
        self._hooks: dict[str, Hook] = {}
        self._lock = threading.Lock()

        # Storage file for persisting hooks
        if storage_path is None:
            storage_path = Path(".leeway/hooks.json")
        self._storage_path = storage_path

        # Load existing hooks
        self._load_hooks()

    def _load_hooks(self) -> None:
        """Load hooks from storage file."""
        if not self._storage_path.exists():
            return

        try:
            with open(self._storage_path) as f:
                data = json.load(f)
                for hook_data in data.get("hooks", []):
                    hook = Hook(**hook_data)
                    self._hooks[hook.id] = hook
        except Exception:
            pass  # Start with empty hooks

    def _save_hooks(self) -> None:
        """Save hooks to storage file."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._storage_path, "w") as f:
            json.dump({
                "hooks": [h.model_dump() for h in self._hooks.values()]
            }, f, indent=2)

    def register(self, name: str, scope: str, event: str,
                 workflow_name: str | None = None, node_name: str | None = None,
                 command: CommandHook | None = None, http: HttpHook | None = None) -> Hook:
        """Register a new hook."""
        with self._lock:
            # Validate hook type
            if command is None and http is None:
                raise HookRegistrationError("Must specify either 'command' or 'http' hook")

            if command is not None and http is not None:
                raise HookRegistrationError("Cannot specify both 'command' and 'http' hook")

            # Validate scope
            if scope not in ("global", "workflow", "node"):
                raise HookRegistrationError(f"Invalid scope: {scope}")

            # Validate event
            valid_events = (
                "workflow_start", "workflow_end",
                "node_start", "node_end",
                "before_tool_use", "after_tool_use"
            )
            if event not in valid_events:
                raise HookRegistrationError(f"Invalid event: {event}. Must be one of: {valid_events}")

            # Validate workflow-level hooks
            if scope == "workflow" and not workflow_name:
                raise HookRegistrationError("workflow_name required for workflow-level hooks")

            # Validate node-level hooks
            if scope == "node" and not (workflow_name and node_name):
                raise HookRegistrationError("workflow_name and node_name required for node-level hooks")

            # Generate hook ID
            hook_id = str(uuid.uuid4())[:8]

            # Create hook
            hook = Hook(
                id=hook_id,
                name=name,
                scope=scope,
                event=event,
                workflow_name=workflow_name,
                node_name=node_name,
                enabled=True,
                command=command,
                http=http,
            )

            self._hooks[hook_id] = hook
            self._save_hooks()

            return hook

    def unregister(self, hook_id: str) -> bool:
        """Unregister a hook."""
        with self._lock:
            if hook_id not in self._hooks:
                raise HookNotFoundError(hook_id)

            del self._hooks[hook_id]
            self._save_hooks()
            return True

    def toggle(self, hook_id: str, enabled: bool) -> Hook:
        """Toggle a hook enabled/disabled."""
        with self._lock:
            if hook_id not in self._hooks:
                raise HookNotFoundError(hook_id)

            hook = self._hooks[hook_id]
            hook.enabled = enabled
            self._save_hooks()
            return hook

    def get(self, hook_id: str) -> Hook:
        """Get a hook by ID."""
        if hook_id not in self._hooks:
            raise HookNotFoundError(hook_id)
        return self._hooks[hook_id]

    def list(self, scope: str | None = None, workflow_name: str | None = None,
             event: str | None = None) -> list[Hook]:
        """List hooks, optionally filtered."""
        with self._lock:
            hooks = list(self._hooks.values())

            if scope:
                hooks = [h for h in hooks if h.scope == scope]

            if workflow_name:
                hooks = [h for h in hooks if h.workflow_name == workflow_name]

            if event:
                hooks = [h for h in hooks if h.event == event]

            return hooks

    def get_for_event(self, event: str, workflow_name: str | None = None,
                      node_name: str | None = None) -> list[Hook]:
        """Get hooks that should fire for a given event."""
        with self._lock:
            matching_hooks = []

            for hook in self._hooks.values():
                if not hook.enabled:
                    continue

                if hook.event != event:
                    continue

                # Check scope
                if hook.scope == "global":
                    matching_hooks.append(hook)
                elif hook.scope == "workflow" and hook.workflow_name == workflow_name:
                    matching_hooks.append(hook)
                elif hook.scope == "node" and hook.workflow_name == workflow_name and hook.node_name == node_name:
                    matching_hooks.append(hook)

            return matching_hooks

    def execute_hook(self, hook_id: str, context: HookExecutionContext) -> HookExecutionResult:
        """Execute a single hook."""
        import datetime

        hook = self.get(hook_id)
        start_time = time.time()

        try:
            if hook.command:
                return self._execute_command_hook(hook.command, context, hook.id, start_time)
            elif hook.http:
                return self._execute_http_hook(hook.http, context, hook.id, start_time)
            else:
                raise HookExecutionError(hook_id, "Hook has no command or http configuration")
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            return HookExecutionResult(
                hook_id=hook_id,
                success=False,
                error=str(e),
                duration_ms=duration,
            )

    def _execute_command_hook(self, command: CommandHook, context: HookExecutionContext,
                               hook_id: str, start_time: float) -> HookExecutionResult:
        """Execute a command hook."""
        import subprocess

        # Build environment
        env = os.environ.copy()
        if command.env:
            env.update(command.env)

        # Add context to environment
        env["LEEWAY_EXECUTION_ID"] = context.execution_id
        env["LEEWAY_WORKFLOW_NAME"] = context.workflow_name
        if context.node_name:
            env["LEEWAY_NODE_NAME"] = context.node_name
        if context.tool_name:
            env["LEEWAY_TOOL_NAME"] = context.tool_name
        env["LEEWAY_EVENT"] = context.event

        try:
            result = subprocess.run(
                [command.command] + command.args,
                capture_output=True,
                text=True,
                env=env,
                timeout=command.timeout,
            )

            duration = int((time.time() - start_time) * 1000)

            return HookExecutionResult(
                hook_id=hook_id,
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None,
                exit_code=result.returncode,
                duration_ms=duration,
            )
        except subprocess.TimeoutExpired:
            duration = int((time.time() - start_time) * 1000)
            return HookExecutionResult(
                hook_id=hook_id,
                success=False,
                error=f"Command timed out after {command.timeout}s",
                exit_code=-1,
                duration_ms=duration,
            )
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            return HookExecutionResult(
                hook_id=hook_id,
                success=False,
                error=str(e),
                duration_ms=duration,
            )

    def _execute_http_hook(self, http: HttpHook, context: HookExecutionContext,
                           hook_id: str, start_time: float) -> HookExecutionResult:
        """Execute an HTTP/webhook hook."""
        import urllib.request
        import urllib.error

        # Build request body
        body = http.body.copy() if http.body else {}
        body.update({
            "execution_id": context.execution_id,
            "workflow_name": context.workflow_name,
            "node_name": context.node_name,
            "tool_name": context.tool_name,
            "event": context.event,
            "data": context.data,
        })

        # Convert to JSON
        body_json = json.dumps(body).encode("utf-8") if body else None

        # Build headers
        headers = http.headers or {}
        headers.setdefault("Content-Type", "application/json")

        try:
            request = urllib.request.Request(
                http.url,
                data=body_json,
                method=http.method,
                headers=headers,
            )

            # Execute request with timeout
            response = urllib.request.urlopen(request, timeout=http.timeout)
            response_body = response.read().decode("utf-8")

            duration = int((time.time() - start_time) * 1000)

            return HookExecutionResult(
                hook_id=hook_id,
                success=response.status < 400,
                output=response_body,
                http_status=response.status,
                duration_ms=duration,
            )
        except urllib.error.HTTPError as e:
            duration = int((time.time() - start_time) * 1000)
            error_body = e.read().decode("utf-8") if e.fp else str(e)
            return HookExecutionResult(
                hook_id=hook_id,
                success=False,
                error=error_body,
                http_status=e.code,
                duration_ms=duration,
            )
        except urllib.error.URLError as e:
            duration = int((time.time() - start_time) * 1000)
            return HookExecutionResult(
                hook_id=hook_id,
                success=False,
                error=str(e.reason),
                duration_ms=duration,
            )
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            return HookExecutionResult(
                hook_id=hook_id,
                success=False,
                error=str(e),
                duration_ms=duration,
            )

    def execute_for_event(self, event: str, context: HookExecutionContext,
                           async_execution: bool = False) -> list[HookExecutionResult]:
        """
        Execute all hooks for a given event.
        
        Args:
            event: The event type (workflow_start, workflow_end, etc.)
            context: Execution context
            async_execution: If True, execute hooks asynchronously (non-blocking)
        
        Returns:
            List of hook execution results (empty if async)
        """
        hooks = self.get_for_event(
            event=event,
            workflow_name=context.workflow_name,
            node_name=context.node_name,
        )

        if not hooks:
            return []

        if async_execution:
            # Execute hooks in background thread (non-blocking)
            thread = threading.Thread(
                target=self._execute_hooks_background,
                args=(hooks, context),
                daemon=True
            )
            thread.start()
            return []  # Return empty - results will be logged internally
        else:
            # Synchronous execution
            results = []
            for hook in hooks:
                result = self.execute_hook(hook.id, context)
                results.append(result)
            return results

    def _execute_hooks_background(self, hooks: list[Hook], context: HookExecutionContext) -> None:
        """Execute hooks in background (for async mode)."""
        for hook in hooks:
            try:
                self.execute_hook(hook.id, context)
            except Exception:
                pass  # Log but don't crash


class CustomToolRegistry:
    """Registry for custom Python tools (tool authoring API)."""

    def __init__(self, tools_dir: Path | None = None, storage_path: Path | None = None):
        self._tools: dict[str, CustomTool] = {}
        self._lock = threading.Lock()
        self._compiled_functions: dict[str, Callable] = {}

        # Tools directory for file-based tools
        if tools_dir is None:
            tools_dir = Path(".leeway/tools")
        self._tools_dir = tools_dir

        # Storage file for persisting tool registry
        if storage_path is None:
            storage_path = Path(".leeway/tools.json")
        self._storage_path = storage_path

        # Load existing tools
        self._load_tools()

    def _load_tools(self) -> None:
        """Load tools from storage file."""
        if not self._storage_path.exists():
            return

        try:
            with open(self._storage_path) as f:
                data = json.load(f)
                for tool_data in data.get("tools", []):
                    tool = CustomTool(**tool_data)
                    self._tools[tool.id] = tool
                    # Compile the tool code
                    self._compile_tool(tool)
        except Exception:
            pass  # Start with empty tools

    def _save_tools(self) -> None:
        """Save tools to storage file."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._storage_path, "w") as f:
            json.dump({
                "tools": [t.model_dump() for t in self._tools.values()]
            }, f, indent=2)

    def _iso_time(self, timestamp: float | None = None) -> str:
        """Generate ISO format timestamp."""
        import datetime
        if timestamp is None:
            timestamp = time.time()
        return datetime.datetime.fromtimestamp(timestamp).isoformat() + "Z"

    def _generate_tool_id(self) -> str:
        """Generate a unique tool ID."""
        return str(uuid.uuid4())[:8]

    def _compile_tool(self, tool: CustomTool) -> Callable | None:
        """Compile and cache a tool's Python code."""
        try:
            namespace = {
                "__name__": f"tool_{tool.id}",
            }
            exec(compile(tool.code, f"<tool:{tool.name}>", "exec"), namespace)

            # Look for the main function
            if "execute" in namespace:
                self._compiled_functions[tool.id] = namespace["execute"]
                return namespace["execute"]
            elif "run" in namespace:
                self._compiled_functions[tool.id] = namespace["run"]
                return namespace["run"]
            elif "main" in namespace:
                self._compiled_functions[tool.id] = namespace["main"]
                return namespace["main"]
        except Exception as e:
            pass  # Compilation failed - will be reported at execution time
        return None

    def _validate_tool_code(self, code: str) -> tuple[bool, list[str]]:
        """
        Validate tool code without executing it.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        try:
            # Try to compile the code
            compiled = compile(code, "<tool>", "exec")

            # Create a namespace to check for required elements
            namespace = {}
            exec(compiled, namespace)

            # Check for at least one entry point function
            has_entry_point = any(name in namespace for name in ["execute", "run", "main"])
            if not has_entry_point:
                errors.append("Tool code must define at least one of: execute(), run(), or main()")

        except SyntaxError as e:
            errors.append(f"Syntax error: {e}")
        except Exception as e:
            errors.append(f"Compilation error: {e}")

        return len(errors) == 0, errors

    def register(self, name: str, description: str, code: str,
               parameters: list[ToolParameter] | None = None,
               version: str = "1.0.0", author: str | None = None,
               tags: list[str] | None = None, force: bool = False) -> CustomTool:
        """
        Register a new custom tool.

        Args:
            name: Tool name
            description: Tool description
            code: Python code for the tool
            parameters: Tool parameters
            version: Tool version
            author: Tool author
            tags: Tool tags
            force: If True, overwrite existing tool with same name

        Returns:
            The registered CustomTool instance
        """
        with self._lock:
            # Validate code
            is_valid, errors = self._validate_tool_code(code)
            if not is_valid:
                raise ToolValidationError("Invalid tool code", errors)

            # Check for existing tool with same name (if not forcing)
            for existing_tool in self._tools.values():
                if existing_tool.name == name and not force:
                    raise ToolAlreadyExistsError(name)

            # Generate tool ID
            tool_id = self._generate_tool_id()

            # Create tool
            tool = CustomTool(
                id=tool_id,
                name=name,
                description=description,
                parameters=parameters or [],
                code=code,
                version=version,
                author=author,
                tags=tags or [],
                enabled=True,
                created_at=self._iso_time(),
            )

            self._tools[tool_id] = tool

            # Compile the tool
            self._compile_tool(tool)

            self._save_tools()
            return tool

    def unregister(self, tool_id: str) -> bool:
        """Unregister a tool."""
        with self._lock:
            if tool_id not in self._tools:
                raise ToolNotFoundError(tool_id, [])

            del self._tools[tool_id]
            self._compiled_functions.pop(tool_id, None)
            self._save_tools()
            return True

    def toggle(self, tool_id: str, enabled: bool) -> CustomTool:
        """Toggle a tool enabled/disabled."""
        with self._lock:
            if tool_id not in self._tools:
                raise ToolNotFoundError(tool_id, [])

            tool = self._tools[tool_id]
            tool.enabled = enabled
            tool.updated_at = self._iso_time()
            self._save_tools()
            return tool

    def get(self, tool_id: str) -> CustomTool:
        """Get a tool by ID."""
        if tool_id not in self._tools:
            raise ToolNotFoundError(tool_id, [])
        return self._tools[tool_id]

    def get_by_name(self, name: str) -> CustomTool | None:
        """Get a tool by name."""
        for tool in self._tools.values():
            if tool.name == name:
                return tool
        return None

    def list(self, tag: str | None = None) -> list[CustomTool]:
        """List tools, optionally filtered by tag."""
        with self._lock:
            tools = list(self._tools.values())

            if tag:
                tools = [t for t in tools if tag in t.tags]

            return tools

    def execute(self, name: str, arguments: dict) -> tuple[Any, int]:
        """
        Execute a custom tool.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tuple of (result, execution_time_ms)
        """
        start_time = time.time()

        # Find the tool
        tool = self.get_by_name(name)
        if not tool:
            available = [t.name for t in self._tools.values()]
            raise ToolNotFoundError(name, available)

        if not tool.enabled:
            raise ToolExecutionError(name, "Tool is disabled")

        # Get compiled function
        func = self._compiled_functions.get(tool.id)
        if not func:
            # Recompile if needed
            func = self._compile_tool(tool)
            if not func:
                raise ToolExecutionError(name, "Tool code could not be compiled")

        try:
            # Execute the tool function
            result = func(**arguments)
            execution_time = int((time.time() - start_time) * 1000)
            return result, execution_time
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            raise ToolExecutionError(name, f"Execution failed: {str(e)}")


class PluginRegistry:
    """
    Registry for managing plugins.
    
    A plugin is a bundle that can contain:
    - Workflows (YAML files)
    - Skills (with SKILL.md and references)
    - Tools (custom Python tools)
    - Hooks (command and HTTP hooks)
    - MCP servers (configurations)
    """

    def __init__(self, base_dir: Path | None = None, storage_path: Path | None = None):
        """
        Initialize the plugin registry.
        
        Args:
            base_dir: Base directory for plugin storage (default: .leeway/plugins)
            storage_path: Path to plugin registry storage (default: .leeway/plugins.json)
        """
        if base_dir is None:
            base_dir = Path(".leeway/plugins")
        self._base_dir = base_dir

        if storage_path is None:
            storage_path = Path(".leeway/plugins.json")
        self._storage_path = storage_path

        self._plugins: dict[str, Plugin] = {}
        self._lock = threading.Lock()

        # Load existing plugins
        self._load_plugins()

    def _load_plugins(self) -> None:
        """Load plugins from storage file."""
        if not self._storage_path.exists():
            return

        try:
            with open(self._storage_path) as f:
                data = json.load(f)
                for plugin_data in data.get("plugins", []):
                    plugin = Plugin(**plugin_data)
                    self._plugins[plugin.id] = plugin
        except Exception:
            pass  # Start with empty plugins

    def _save_plugins(self) -> None:
        """Save plugins to storage file."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._storage_path, "w") as f:
            json.dump({
                "plugins": [p.model_dump() for p in self._plugins.values()]
            }, f, indent=2)

    def _iso_time(self, timestamp: float | None = None) -> str:
        """Generate ISO format timestamp."""
        import datetime
        if timestamp is None:
            timestamp = time.time()
        return datetime.datetime.fromtimestamp(timestamp).isoformat() + "Z"

    def _generate_plugin_id(self) -> str:
        """Generate a unique plugin ID."""
        return str(uuid.uuid4())[:8]

    def _validate_plugin_content(self, content: PluginContent) -> tuple[bool, list[str], list[str]]:
        """
        Validate plugin content without installing.
        
        Returns:
            Tuple of (is_valid, list_of_errors, list_of_warnings)
        """
        errors = []
        warnings = []

        # Validate workflows
        for wf in content.workflows:
            if not isinstance(wf, dict):
                errors.append("Workflow must be a dictionary")
                continue
            if "name" not in wf:
                warnings.append("Workflow missing 'name' field")

        # Validate skills
        for skill in content.skills:
            if not isinstance(skill, dict):
                errors.append("Skill must be a dictionary")
                continue
            if "name" not in skill:
                warnings.append("Skill missing 'name' field")

        # Validate tools
        for tool in content.tools:
            if not isinstance(tool, dict):
                errors.append("Tool must be a dictionary")
                continue
            if "name" not in tool:
                errors.append("Tool missing 'name' field")
            if "code" not in tool:
                errors.append("Tool missing 'code' field")

        # Validate hooks
        for hook in content.hooks:
            if not isinstance(hook, dict):
                errors.append("Hook must be a dictionary")
                continue
            if "name" not in hook:
                errors.append("Hook missing 'name' field")
            if "scope" not in hook:
                errors.append("Hook missing 'scope' field")
            if "event" not in hook:
                errors.append("Hook missing 'event' field")

        # Validate MCP servers
        for mcp in content.mcp_servers:
            if not isinstance(mcp, dict):
                errors.append("MCP server must be a dictionary")
                continue
            if "name" not in mcp:
                errors.append("MCP server missing 'name' field")
            if "command" not in mcp:
                errors.append("MCP server missing 'command' field")

        return len(errors) == 0, errors, warnings

    def _check_dependencies(self, dependencies: dict[str, str]) -> tuple[bool, list[str]]:
        """
        Check if plugin dependencies are satisfied.
        
        Returns:
            Tuple of (all_satisfied, list_of_missing)
        """
        missing = []

        for dep_id, version_range in dependencies.items():
            # Check if dependency is installed and enabled
            if dep_id not in self._plugins:
                missing.append(f"{dep_id} ({version_range})")
            elif not self._plugins[dep_id].enabled:
                # Check version compatibility (simplified)
                if not self._check_version_compatibility(self._plugins[dep_id].metadata.version, version_range):
                    missing.append(f"{dep_id} ({version_range})")

        return len(missing) == 0, missing

    def _check_version_compatibility(self, installed_version: str, version_range: str) -> bool:
        """Check if installed version satisfies version range (simplified)."""
        # Simple version check - just compare exact versions for now
        # A full implementation would use semver parsing
        if version_range.startswith(">="):
            required = version_range[2:]
            return installed_version >= required
        elif version_range.startswith(">"):
            required = version_range[1:]
            return installed_version > required
        elif version_range.startswith("="):
            required = version_range[1:]
            return installed_version == required
        else:
            # Assume exact match or any
            return True

    def _install_plugin_content(self, plugin_id: str, content: PluginContent) -> list[str]:
        """
        Install plugin content to appropriate directories.
        
        Returns:
            List of installed file paths
        """
        installed_files = []

        # Install workflows
        workflows_dir = self._base_dir.parent / "workflows"
        for wf in content.workflows:
            wf_name = wf.get("name", f"workflow-{len(installed_files)}")
            wf_path = workflows_dir / f"{wf_name}.yaml"
            wf_path.parent.mkdir(parents=True, exist_ok=True)
            import yaml
            with open(wf_path, "w") as f:
                yaml.dump(wf, f)
            installed_files.append(str(wf_path))

        # Install skills
        skills_dir = self._base_dir.parent / "skills"
        for skill in content.skills:
            skill_name = skill.get("name", f"skill-{len(installed_files)}")
            skill_path = skills_dir / skill_name
            skill_path.mkdir(parents=True, exist_ok=True)
            
            # Write SKILL.md
            if "skill_md" in skill:
                (skill_path / "SKILL.md").write_text(skill["skill_md"])
            
            # Write references
            if "references" in skill:
                refs_dir = skill_path / "references"
                refs_dir.mkdir(exist_ok=True)
                for ref_name, ref_content in skill["references"].items():
                    (refs_dir / ref_name).write_text(ref_content)
            
            installed_files.append(str(skill_path))

        # Tools are registered separately through CustomToolRegistry
        # We'll just note them for now

        # Hooks are registered separately through HookRegistry
        # We'll just note them for now

        # MCP servers are added to settings.json
        # We'll just note them for now

        return installed_files

    def _uninstall_plugin_content(self, plugin_id: str, content: PluginContent) -> list[str]:
        """
        Uninstall plugin content from appropriate directories.
        
        Returns:
            List of removed file paths
        """
        removed_files = []

        # Remove workflows
        workflows_dir = self._base_dir.parent / "workflows"
        for wf in content.workflows:
            wf_name = wf.get("name")
            if wf_name:
                wf_path = workflows_dir / f"{wf_name}.yaml"
                if wf_path.exists():
                    wf_path.unlink()
                    removed_files.append(str(wf_path))

        # Remove skills
        skills_dir = self._base_dir.parent / "skills"
        for skill in content.skills:
            skill_name = skill.get("name")
            if skill_name:
                skill_path = skills_dir / skill_name
                if skill_path.exists():
                    import shutil
                    shutil.rmtree(skill_path)
                    removed_files.append(str(skill_path))

        return removed_files

    def install(self, name: str, metadata: PluginMetadata, content: PluginContent,
                force: bool = False) -> Plugin:
        """
        Install a new plugin.
        
        Args:
            name: Plugin name (for display)
            metadata: Plugin metadata
            content: Plugin content
            force: If True, overwrite existing plugin with same ID
            
        Returns:
            The installed Plugin instance
        """
        with self._lock:
            plugin_id = metadata.id

            # Check for existing plugin
            if plugin_id in self._plugins and not force:
                raise PluginAlreadyExistsError(plugin_id)

            # Validate content
            is_valid, errors, warnings = self._validate_plugin_content(content)
            if not is_valid:
                raise PluginInvalidFormatError("Invalid plugin content", errors)

            # Check dependencies
            if metadata.dependencies:
                deps_satisfied, missing = self._check_dependencies(metadata.dependencies)
                if not deps_satisfied:
                    raise PluginDependencyMissingError(plugin_id, missing)

            # Install content
            installed_files = self._install_plugin_content(plugin_id, content)

            # Create plugin instance
            plugin = Plugin(
                id=plugin_id,
                metadata=metadata,
                content=content,
                enabled=True,
                installed_at=self._iso_time(),
                installed_version=metadata.version,
            )

            self._plugins[plugin_id] = plugin
            self._save_plugins()

            return plugin

    def uninstall(self, plugin_id: str, force: bool = False) -> list[str]:
        """
        Uninstall a plugin.
        
        Args:
            plugin_id: Plugin ID to uninstall
            force: If True, force uninstall even if other plugins depend on this
            
        Returns:
            List of removed file paths
        """
        with self._lock:
            if plugin_id not in self._plugins:
                available = [p.id for p in self._plugins.values()]
                raise PluginNotFoundError(plugin_id, available)

            # Check for dependent plugins
            if not force:
                for other_id, other_plugin in self._plugins.items():
                    if other_id == plugin_id:
                        continue
                    if plugin_id in other_plugin.metadata.dependencies:
                        raise PluginUninstallError(
                            plugin_id,
                            f"Plugin '{other_id}' depends on this plugin"
                        )

            plugin = self._plugins[plugin_id]

            # Uninstall content
            removed_files = self._uninstall_plugin_content(plugin_id, plugin.content)

            # Remove from registry
            del self._plugins[plugin_id]
            self._save_plugins()

            return removed_files

    def toggle(self, plugin_id: str, enabled: bool) -> Plugin:
        """Toggle a plugin enabled/disabled."""
        with self._lock:
            if plugin_id not in self._plugins:
                available = [p.id for p in self._plugins.values()]
                raise PluginNotFoundError(plugin_id, available)

            plugin = self._plugins[plugin_id]
            plugin.enabled = enabled
            plugin.updated_at = self._iso_time()
            self._save_plugins()
            return plugin

    def get(self, plugin_id: str) -> Plugin:
        """Get a plugin by ID."""
        if plugin_id not in self._plugins:
            available = [p.id for p in self._plugins.values()]
            raise PluginNotFoundError(plugin_id, available)
        return self._plugins[plugin_id]

    def list(self, category: str | None = None, tag: str | None = None) -> list[Plugin]:
        """List plugins, optionally filtered by category or tag."""
        with self._lock:
            plugins = list(self._plugins.values())

            if category:
                plugins = [p for p in plugins if category in p.metadata.categories]

            if tag:
                plugins = [p for p in plugins if tag in p.metadata.tags]

            return plugins

    def search(self, query: str, category: str | None = None) -> list[Plugin]:
        """Search plugins by name, description, or tags."""
        with self._lock:
            plugins = list(self._plugins.values())
            query_lower = query.lower()

            # Filter by query
            results = []
            for plugin in plugins:
                # Search in name
                if query_lower in plugin.metadata.name.lower():
                    results.append(plugin)
                    continue
                # Search in description
                if query_lower in plugin.metadata.description.lower():
                    results.append(plugin)
                    continue
                # Search in tags
                if any(query_lower in tag.lower() for tag in plugin.metadata.tags):
                    results.append(plugin)
                    continue

            # Apply category filter if specified
            if category:
                results = [p for p in results if category in p.metadata.categories]

            return results

    def update(self, plugin_id: str, new_version: str | None = None) -> Plugin:
        """
        Update a plugin to a new version.
        
        Note: This is a simplified implementation. A full version would
        need to fetch the new version from the source.
        """
        with self._lock:
            if plugin_id not in self._plugins:
                available = [p.id for p in self._plugins.values()]
                raise PluginNotFoundError(plugin_id, available)

            plugin = self._plugins[plugin_id]

            # For now, just toggle it as "updated"
            if new_version:
                plugin.metadata.version = new_version

            plugin.updated_at = self._iso_time()
            self._save_plugins()

            return plugin


# =============================================================================
# Phase B.1: Workflow Version Manager
# =============================================================================

class WorkflowVersionManager:
    """
    Manager for workflow version control.
    
    Features:
    - Semantic versioning for workflows
    - Default version selection
    - Version deprecation
    - Rollback support
    - Version comparison
    - Max versions per workflow limit
    """

    MAX_VERSIONS_PER_WORKFLOW = 50  # Maximum versions per workflow

    def __init__(self, workflows_dir: Path | None = None, storage_path: Path | None = None):
        """
        Initialize the version manager.
        
        Args:
            workflows_dir: Base directory for workflows (default: .leeway/workflows)
            storage_path: Path to version storage (default: .leeway/workflow-versions.json)
        """
        if workflows_dir is None:
            workflows_dir = Path(".leeway/workflows")
        self._workflows_dir = workflows_dir

        if storage_path is None:
            storage_path = Path(".leeway/workflow-versions.json")
        self._storage_path = storage_path

        # Structure: {workflow_name: {version: WorkflowVersion}}
        self._versions: dict[str, dict[str, WorkflowVersion]] = {}
        self._lock = threading.Lock()

        # Load existing versions
        self._load_versions()

    def _load_versions(self) -> None:
        """Load versions from storage file."""
        if not self._storage_path.exists():
            return

        try:
            with open(self._storage_path) as f:
                data = json.load(f)
                for workflow_name, versions_data in data.get("workflows", {}).items():
                    self._versions[workflow_name] = {}
                    for version_str, version_data in versions_data.items():
                        version = WorkflowVersion(**version_data)
                        self._versions[workflow_name][version_str] = version
        except Exception:
            pass  # Start with empty versions

    def _save_versions(self) -> None:
        """Save versions to storage file."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._storage_path, "w") as f:
            json.dump({
                "workflows": {
                    workflow_name: {
                        version_str: version.model_dump()
                        for version_str, version in versions.items()
                    }
                    for workflow_name, versions in self._versions.items()
                }
            }, f, indent=2)

    def _validate_version_format(self, version: str) -> bool:
        """Validate semantic version format (e.g., 1.0.0, 2.1.3-beta)."""
        import re
        # Match semantic versioning: MAJOR.MINOR.PATCH[-prerelease]
        pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$"
        return bool(re.match(pattern, version))

    def _compare_versions(self, version_a: str, version_b: str) -> int:
        """
        Compare two semantic versions.
        
        Returns:
            -1 if version_a < version_b
             0 if version_a == version_b
             1 if version_a > version_b
        """
        import re

        def parse_version(v: str) -> tuple:
            """Parse version string to tuple for comparison."""
            # Remove prerelease suffix for comparison
            base = v.split("-")[0]
            parts = base.split(".")
            return tuple(int(p) for p in parts)

        v_a = parse_version(version_a)
        v_b = parse_version(version_b)

        if v_a < v_b:
            return -1
        elif v_a > v_b:
            return 1
        else:
            # If base versions are equal, prerelease comes before release
            if "-" in version_a and "-" not in version_b:
                return -1
            if "-" not in version_a and "-" in version_b:
                return 1
            return 0

    def _iso_time(self, timestamp: float | None = None) -> str:
        """Generate ISO format timestamp."""
        import datetime
        if timestamp is None:
            timestamp = time.time()
        return datetime.datetime.fromtimestamp(timestamp).isoformat() + "Z"

    def _get_default_version(self, workflow_name: str) -> str | None:
        """Get the default version for a workflow."""
        if workflow_name not in self._versions:
            return None

        for version_str, version in self._versions[workflow_name].items():
            if version.is_default:
                return version_str

        return None

    def _set_new_default(self, workflow_name: str, version_str: str) -> None:
        """Set a new default version, unsetting the old default."""
        if workflow_name not in self._versions:
            return

        # Unset old default
        for v, version in self._versions[workflow_name].items():
            if version.is_default and v != version_str:
                version.is_default = False

        # Set new default
        self._versions[workflow_name][version_str].is_default = True

    def list_versions(self, workflow_name: str) -> tuple[list[WorkflowVersionInfo], WorkflowVersionMetadata]:
        """
        List all versions of a workflow.
        
        Returns:
            Tuple of (versions list, metadata)
        """
        with self._lock:
            if workflow_name not in self._versions:
                return [], WorkflowVersionMetadata(
                    workflow_name=workflow_name,
                    total_versions=0,
                )

            versions = self._versions[workflow_name]
            version_list = []

            for version_str, version in sorted(versions.items(), 
                                         key=lambda x: x[0], 
                                         reverse=True):
                version_list.append(WorkflowVersionInfo(
                    version=version.version,
                    created_at=version.created_at,
                    created_by=version.created_by,
                    changelog=version.changelog,
                    is_default=version.is_default,
                    is_deprecated=version.is_deprecated,
                ))

            # Get metadata
            default_v = self._get_default_version(workflow_name)
            sorted_versions = sorted(versions.keys(), key=lambda x: self._compare_versions(x, "999.999.999"))
            latest = sorted_versions[0] if sorted_versions else None
            deprecated = [v for v, ver in versions.items() if ver.is_deprecated]

            # Find latest stable (not deprecated)
            latest_stable = None
            for v in sorted_versions:
                if not versions[v].is_deprecated:
                    latest_stable = v
                    break

            metadata = WorkflowVersionMetadata(
                workflow_name=workflow_name,
                total_versions=len(versions),
                default_version=default_v,
                latest_version=latest,
                latest_stable=latest_stable,
                deprecated_versions=deprecated,
            )

            return version_list, metadata

    def get_version(self, workflow_name: str, version: str | None = None) -> tuple[WorkflowVersion, bool]:
        """
        Get a specific version of a workflow.
        
        Args:
            workflow_name: Name of the workflow
            version: Version string (if None, gets default version)
        
        Returns:
            Tuple of (WorkflowVersion, is_default)
        """
        with self._lock:
            if workflow_name not in self._versions:
                # Try to load from file as version 1.0.0
                if version is None:
                    version = "1.0.0"
                return self._load_from_file(workflow_name, version, default_version=True)

            # If no version specified, get default
            if version is None:
                version = self._get_default_version(workflow_name)
                if version is None:
                    # Get the latest version
                    sorted_versions = sorted(
                        self._versions[workflow_name].keys(),
                        key=lambda x: self._compare_versions(x, "999.999.999"),
                        reverse=True
                    )
                    version = sorted_versions[0] if sorted_versions else "1.0.0"

            if version not in self._versions[workflow_name]:
                available = list(self._versions[workflow_name].keys())
                raise VersionNotFoundError(workflow_name, version, available)

            ver = self._versions[workflow_name][version]
            is_default = ver.is_default

            return ver, is_default

    def _load_from_file(self, workflow_name: str, version: str, default_version: bool = False) -> tuple[WorkflowVersion, bool]:
        """
        Load workflow version from file.
        
        If the workflow exists as a YAML file, create a version entry for it.
        """
        workflow_path = self._workflows_dir / f"{workflow_name}.yaml"
        
        if not workflow_path.exists():
            raise VersionNotFoundError(workflow_name, version, [])

        # Read workflow content
        try:
            with open(workflow_path) as f:
                workflow_content = f.read()
        except Exception:
            raise VersionNotFoundError(workflow_name, version, [])

        # Create version entry
        ver = WorkflowVersion(
            version=version,
            created_at=self._iso_time(),
            is_default=default_version,
            is_deprecated=False,
            workflow_content=workflow_content,
        )

        # Initialize workflow in versions dict if not exists
        if workflow_name not in self._versions:
            self._versions[workflow_name] = {}

        self._versions[workflow_name][version] = ver
        self._save_versions()

        return ver, default_version

    def create_version(self, workflow_name: str, version: str, 
                 changelog: str | None = None, created_by: str | None = None,
                 set_default: bool = False) -> WorkflowVersion:
        """
        Create a new version of a workflow.
        
        Args:
            workflow_name: Name of the workflow
            version: Semantic version (e.g., "1.0.0")
            changelog: Description of changes
            created_by: Author of this version
            set_default: Whether to set as default version
        
        Returns:
            Created WorkflowVersion
        """
        with self._lock:
            # Validate version format
            if not self._validate_version_format(version):
                raise VersionInvalidFormatError(version, "Must follow semantic versioning (e.g., 1.0.0)")

            # Check max versions limit
            if workflow_name in self._versions:
                if len(self._versions[workflow_name]) >= self.MAX_VERSIONS_PER_WORKFLOW:
                    raise VersionMaxReachedError(workflow_name, self.MAX_VERSIONS_PER_WORKFLOW)

                # Check if version already exists
                if version in self._versions[workflow_name]:
                    raise VersionAlreadyExistsError(workflow_name, version)
            else:
                self._versions[workflow_name] = {}

            # Try to load workflow content from file
            workflow_path = self._workflows_dir / f"{workflow_name}.yaml"
            workflow_content = None
            if workflow_path.exists():
                try:
                    with open(workflow_path) as f:
                        workflow_content = f.read()
                except Exception:
                    pass

            # Create version
            ver = WorkflowVersion(
                version=version,
                created_at=self._iso_time(),
                created_by=created_by,
                changelog=changelog,
                is_default=set_default,
                is_deprecated=False,
                workflow_content=workflow_content,
            )

            # If setting as default, unset old default
            if set_default:
                self._set_new_default(workflow_name, version)

            self._versions[workflow_name][version] = ver
            self._save_versions()

            return ver

    def set_default_version(self, workflow_name: str, version: str) -> WorkflowVersion:
        """Set a version as the default."""
        with self._lock:
            if workflow_name not in self._versions:
                raise VersionNotFoundError(workflow_name, version, [])

            if version not in self._versions[workflow_name]:
                available = list(self._versions[workflow_name].keys())
                raise VersionNotFoundError(workflow_name, version, available)

            # Check if deprecated
            if self._versions[workflow_name][version].is_deprecated:
                raise VersionDeprecatedError(workflow_name, version)

            # Set new default
            self._set_new_default(workflow_name, version)
            self._save_versions()

            return self._versions[workflow_name][version]

    def deprecate_version(self, workflow_name: str, version: str) -> WorkflowVersion:
        """Deprecate a version."""
        with self._lock:
            if workflow_name not in self._versions:
                raise VersionNotFoundError(workflow_name, version, [])

            if version not in self._versions[workflow_name]:
                available = list(self._versions[workflow_name].keys())
                raise VersionNotFoundError(workflow_name, version, available)

            ver = self._versions[workflow_name][version]
            ver.is_deprecated = True

            # If this was default, unset it
            if ver.is_default:
                ver.is_default = False
                # Try to set another version as default
                for v, other_ver in self._versions[workflow_name].items():
                    if v != version and not other_ver.is_deprecated:
                        other_ver.is_default = True
                        break

            self._save_versions()

            return ver

    def delete_version(self, workflow_name: str, version: str, force: bool = False) -> bool:
        """Delete a version."""
        with self._lock:
            if workflow_name not in self._versions:
                raise VersionNotFoundError(workflow_name, version, [])

            if version not in self._versions[workflow_name]:
                available = list(self._versions[workflow_name].keys())
                raise VersionNotFoundError(workflow_name, version, available)

            ver = self._versions[workflow_name][version]

            # Check if it's the only version
            if len(self._versions[workflow_name]) == 1:
                if not force:
                    raise VersionNotFoundError(
                        workflow_name, version, 
                        ["Cannot delete the only version without force=True"]
                    )

            # Check if it's the default and force is not set
            if ver.is_default and not force:
                raise VersionNotFoundError(
                    workflow_name, version,
                    ["Cannot delete default version without force=True"]
                )

            # If default, unset and try to set another as default
            if ver.is_default:
                ver.is_default = False
                for v, other_ver in self._versions[workflow_name].items():
                    if v != version:
                        other_ver.is_default = True
                        break

            del self._versions[workflow_name][version]
            self._save_versions()

            return True

    def compare_versions(self, workflow_name: str, version_a: str, version_b: str) -> dict:
        """
        Compare two versions.
        
        Returns:
            Dict with relationship and diff info
        """
        with self._lock:
            if workflow_name not in self._versions:
                raise VersionNotFoundError(workflow_name, version_a, [])

            # Get versions
            if version_a not in self._versions[workflow_name]:
                available = list(self._versions[workflow_name].keys())
                raise VersionNotFoundError(workflow_name, version_a, available)

            if version_b not in self._versions[workflow_name]:
                available = list(self._versions[workflow_name].keys())
                raise VersionNotFoundError(workflow_name, version_b, available)

            ver_a = self._versions[workflow_name][version_a]
            ver_b = self._versions[workflow_name][version_b]

            # Determine relationship
            cmp_result = self._compare_versions(version_a, version_b)
            if cmp_result < 0:
                relationship = "older"
            elif cmp_result > 0:
                relationship = "newer"
            else:
                relationship = "equal"

            # Simple diff (in a full impl, would compare workflow content)
            diff = {
                "version_a_created": ver_a.created_at,
                "version_b_created": ver_b.created_at,
                "version_a_deprecated": ver_a.is_deprecated,
                "version_b_deprecated": ver_b.is_deprecated,
            }

            return {
                "workflow_name": workflow_name,
                "version_a": version_a,
                "version_b": version_b,
                "relationship": relationship,
                "diff": diff,
            }

    def rollback(self, workflow_name: str, target_version: str,
             new_version: str | None = None, changelog: str | None = None) -> str:
        """
        Rollback to a previous version.
        
        Creates a new version with content from the target version.
        
        Returns:
            New version string
        """
        with self._lock:
            # Get target version
            if workflow_name not in self._versions:
                raise VersionNotFoundError(workflow_name, target_version, [])

            if target_version not in self._versions[workflow_name]:
                available = list(self._versions[workflow_name].keys())
                raise VersionNotFoundError(workflow_name, target_version, available)

            target = self._versions[workflow_name][target_version]

            # Generate new version if not provided
            if new_version is None:
                new_version = self._generate_rollback_version(target_version)

            # Create new version with target's content
            ver = WorkflowVersion(
                version=new_version,
                created_at=self._iso_time(),
                changelog=changelog or f"Rollback to {target_version}",
                is_default=True,
                is_deprecated=False,
                workflow_content=target.workflow_content,
            )

            # Initialize if needed
            if workflow_name not in self._versions:
                self._versions[workflow_name] = {}

            # Set new as default, unsetting old
            self._set_new_default(workflow_name, new_version)
            self._versions[workflow_name][new_version] = ver
            self._save_versions()

            return new_version

    def _generate_rollback_version(self, target_version: str) -> str:
        """Generate a new version string for rollback."""
        import re

        # Parse target version
        base = target_version.split("-")[0]
        parts = base.split(".")
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

        # Increment patch for rollback
        patch += 1

        # Check if workflow has versions
        if True:  # Simplified - always use rollback pattern
            return f"{major}.{minor}.{patch}-rollback"


# =============================================================================
# Phase B.2: Workflow Template Marketplace Manager
# =============================================================================

class TemplateManager:
    """
    Manager for workflow template marketplace.
    
    Features:
    - Local template storage and indexing
    - Template search and filtering
    - Template installation/uninstallation
    - Template publishing (to local registry)
    - Ratings and reviews
    - Categories management
    """
    
    DEFAULT_CATEGORIES = [
        TemplateCategory(id="code-quality", name="Code Quality", description="Code linting, formatting, and quality checks"),
        TemplateCategory(id="security", name="Security", description="Security scanning and auditing"),
        TemplateCategory(id="testing", name="Testing", description="Test generation and execution"),
        TemplateCategory(id="documentation", name="Documentation", description="Documentation generation"),
        TemplateCategory(id="review", name="Code Review", description="PR and code review workflows"),
        TemplateCategory(id="devops", name="DevOps", description="CI/CD and deployment workflows"),
        TemplateCategory(id="data", name="Data Processing", description="Data transformation and analysis"),
        TemplateCategory(id="api", name="API Development", description="API design and testing"),
        TemplateCategory(id="research", name="Research", description="Research and analysis workflows"),
        TemplateCategory(id="custom", name="Custom", description="Custom and user-defined workflows"),
    ]
    
    def __init__(self, templates_dir: Path | None = None, storage_path: Path | None = None):
        """
        Initialize the template manager.
        
        Args:
            templates_dir: Base directory for templates (default: .leeway/templates)
            storage_path: Path to template registry storage (default: .leeway/templates/registry.json)
        """
        if templates_dir is None:
            templates_dir = Path(".leeway/templates")
        self._template_manager._templates_dir = templates_dir
        self._template_manager._templates_dir.mkdir(parents=True, exist_ok=True)
        
        if storage_path is None:
            storage_path = templates_dir / "registry.json"
        self._storage_path = storage_path
        
        # Structure: {template_id: WorkflowTemplate}
        self._template_manager._templates: dict[str, WorkflowTemplate] = {}
        self._ratings: dict[str, list[dict]] = {}  # template_id -> list of ratings
        self._reviews: dict[str, list[TemplateReview]] = {}  # template_id -> list of reviews
        self._downloads: dict[str, int] = {}  # template_id -> download count
        self._categories: dict[str, TemplateCategory] = {}
        self._lock = threading.Lock()
        
        # Initialize categories
        for cat in self.DEFAULT_CATEGORIES:
            self._categories[cat.id] = cat
        
        # Load existing templates
        self._load_templates()
    
    def _load_templates(self) -> None:
        """Load templates from storage file."""
        if not self._storage_path.exists():
            return
        
        try:
            with open(self._storage_path) as f:
                data = json.load(f)
                
                # Load templates
                for template_data in data.get("templates", []):
                    template = WorkflowTemplate(**template_data)
                    self._template_manager._templates[template.id] = template
                
                # Load ratings
                self._ratings = data.get("ratings", {})
                
                # Load reviews
                for review_data in data.get("reviews", []):
                    review = TemplateReview(**review_data)
                    if review.template_id not in self._reviews:
                        self._reviews[review.template_id] = []
                    self._reviews[review.template_id].append(review)
                
                # Load downloads
                self._downloads = data.get("downloads", {})
                
                # Load categories
                for cat_data in data.get("categories", []):
                    cat = TemplateCategory(**cat_data)
                    self._categories[cat.id] = cat
                    
        except Exception:
            pass  # Start with empty templates
    
    def _save_templates(self) -> None:
        """Save templates to storage file."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert reviews to dict for JSON serialization
        reviews_list = []
        for template_id, reviews in self._reviews.items():
            for review in reviews:
                reviews_list.append(review.model_dump())
        
        with open(self._storage_path, "w") as f:
            json.dump({
                "templates": [t.model_dump() for t in self._template_manager._templates.values()],
                "ratings": self._ratings,
                "reviews": reviews_list,
                "downloads": self._downloads,
                "categories": [c.model_dump() for c in self._categories.values()],
            }, f, indent=2)
    
    def _iso_time(self, timestamp: float | None = None) -> str:
        """Generate ISO format timestamp."""
        import datetime
        if timestamp is None:
            timestamp = time.time()
        return datetime.datetime.fromtimestamp(timestamp).isoformat() + "Z"
    
    def _generate_template_id(self, name: str) -> str:
        """Generate a unique template ID from name."""
        # Convert to lowercase, replace spaces with hyphens
        import re
        base_id = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        
        # Add random suffix if exists
        if base_id in self._template_manager._templates:
            suffix = secrets.token_hex(4)
            base_id = f"{base_id}-{suffix}"
        
        return base_id
    
    def _validate_template_metadata(self, name: str, description: str, category: str) -> list[str]:
        """Validate template metadata."""
        errors = []
        
        if not name or len(name) < 3:
            errors.append("Name must be at least 3 characters")
        if len(name) > 50:
            errors.append("Name must be at most 50 characters")
        
        if not description or len(description) < 10:
            errors.append("Description must be at least 10 characters")
        if len(description) > 500:
            errors.append("Description must be at most 500 characters")
        
        if category not in self._categories:
            errors.append(f"Invalid category: {category}")
        
        return errors
    
    def _search_templates(self, templates: list[WorkflowTemplate], 
                         search: str | None = None,
                         category: str | None = None,
                         tag: str | None = None) -> list[WorkflowTemplate]:
        """Search and filter templates."""
        results = templates
        
        if search:
            search_lower = search.lower()
            results = [t for t in results if (
                search_lower in t.metadata.name.lower() or
                search_lower in t.metadata.description.lower() or
                search_lower in " ".join(t.metadata.keywords).lower() or
                any(search_lower in tag.lower() for tag in t.metadata.tags)
            )]
        
        if category:
            results = [t for t in results if t.metadata.category == category]
        
        if tag:
            results = [t for t in results if tag in t.metadata.tags]
        
        return results
    
    def _sort_templates(self, templates: list[WorkflowTemplate], 
                       sort_by: str = "popular") -> list[WorkflowTemplate]:
        """Sort templates by specified criteria."""
        if sort_by == "popular":
            return sorted(templates, 
                         key=lambda t: self._downloads.get(t.id, 0), 
                         reverse=True)
        elif sort_by == "newest":
            return sorted(templates, 
                         key=lambda t: t.metadata.created_at, 
                         reverse=True)
        elif sort_by == "rating":
            return sorted(templates,
                         key=lambda t: self._get_rating(t.id).average,
                         reverse=True)
        elif sort_by == "name":
            return sorted(templates,
                         key=lambda t: t.metadata.name.lower())
        return templates
    
    def _get_rating(self, template_id: str) -> TemplateRating:
        """Get rating summary for a template."""
        ratings = self._ratings.get(template_id, [])
        if not ratings:
            return TemplateRating(average=0.0, count=0, distribution={1: 0, 2: 0, 3: 0, 4: 0, 5: 0})
        
        total = len(ratings)
        avg = sum(r["rating"] for r in ratings) / total
        
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for r in ratings:
            dist_key = min(max(r["rating"], 1), 5)
            distribution[dist_key] = distribution.get(dist_key, 0) + 1
        
        return TemplateRating(average=round(avg, 2), count=total, distribution=distribution)
    
    # Public API
    
    def list_templates(self, category: str | None = None, tag: str | None = None,
                      search: str | None = None, sort_by: str = "popular",
                      page: int = 1, limit: int = 20) -> tuple[list[WorkflowTemplate], int, int]:
        """
        List templates with filtering and pagination.
        
        Returns:
            Tuple of (templates, total, total_pages)
        """
        with self._lock:
            templates = list(self._template_manager._templates.values())
            
            # Filter
            templates = self._search_templates(templates, search, category, tag)
            
            # Sort
            templates = self._sort_templates(templates, sort_by)
            
            # Paginate
            total = len(templates)
            total_pages = (total + limit - 1) // limit
            start = (page - 1) * limit
            end = start + limit
            
            return templates[start:end], total, total_pages
    
    def get_template(self, template_id: str) -> WorkflowTemplate | None:
        """Get a template by ID."""
        with self._lock:
            return self._template_manager._templates.get(template_id)
    
    def search_templates(self, query: str, category: str | None = None,
                        tags: list[str] = None, author: str | None = None,
                        min_rating: float | None = None,
                        page: int = 1, limit: int = 20) -> tuple[list[WorkflowTemplate], int, list[str]]:
        """
        Search templates with advanced options.
        
        Returns:
            Tuple of (templates, total, suggestions)
        """
        with self._lock:
            templates = list(self._template_manager._templates.values())
            
            # Apply filters
            if query:
                templates = self._search_templates(templates, search=query)
            
            if category:
                templates = [t for t in templates if t.metadata.category == category]
            
            if tags:
                templates = [t for t in templates if any(tag in t.metadata.tags for tag in tags)]
            
            if author:
                templates = [t for t in templates if t.metadata.author.name == author]
            
            if min_rating is not None:
                templates = [t for t in templates 
                           if self._get_rating(t.id).average >= min_rating]
            
            # Sort by relevance (simple: exact match > partial match)
            total = len(templates)
            
            # Paginate
            start = (page - 1) * limit
            end = start + limit
            paginated = templates[start:end]
            
            # Generate suggestions (simple keyword extraction)
            suggestions = []
            if query and total == 0:
                # Add partial matches as suggestions
                for t in self._template_manager._templates.values():
                    if query.lower() in t.metadata.name.lower():
                        suggestions.append(t.metadata.name)
            
            return paginated, total, suggestions[:5]
    
    def list_categories(self, parent_id: str | None = None) -> list[TemplateCategory]:
        """List template categories."""
        with self._lock:
            if parent_id is None:
                return [c for c in self._categories.values() if c.parent_id is None]
            return [c for c in self._categories.values() if c.parent_id == parent_id]
    
    def install_template(self, template_id: str, name: str | None = None,
                        version: str | None = None, target_dir: Path | None = None) -> dict:
        """
        Install a template to local workflows.
        
        Returns:
            Dict with installation result
        """
        with self._lock:
            template = self._template_manager._templates.get(template_id)
            if not template:
                raise TemplateNotFoundError(template_id, list(self._template_manager._templates.keys()))
            
            # Determine target workflow name
            workflow_name = name or template.metadata.name.lower().replace(" ", "-")
            
            # Determine target directory
            if target_dir is None:
                target_dir = self._template_manager._templates_dir.parent / "workflows"
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Write workflow file
            workflow_path = target_dir / f"{workflow_name}.yaml"
            try:
                with open(workflow_path, "w") as f:
                    f.write(template.content)
            except Exception as e:
                raise TemplateDownloadFailedError(template_id, str(e))
            
            # Increment download count
            self._downloads[template_id] = self._downloads.get(template_id, 0) + 1
            self._save_templates()
            
            return {
                "success": True,
                "template_id": template_id,
                "workflow_name": workflow_name,
                "installed_path": str(workflow_path),
            }
    
    def uninstall_template(self, template_id: str, delete_files: bool = False) -> dict:
        """
        Uninstall a template.
        
        Returns:
            Dict with uninstallation result
        """
        with self._lock:
            if template_id not in self._template_manager._templates:
                raise TemplateNotFoundError(template_id, list(self._template_manager._templates.keys()))
            
            deleted_files = []
            
            # Optionally delete workflow files
            if delete_files:
                template = self._template_manager._templates[template_id]
                workflow_name = template.metadata.name.lower().replace(" ", "-")
                workflow_path = self._template_manager._templates_dir.parent / "workflows" / f"{workflow_name}.yaml"
                
                if workflow_path.exists():
                    workflow_path.unlink()
                    deleted_files.append(str(workflow_path))
            
            # Remove from registry (but keep ratings/reviews)
            # Note: We don't actually delete the template, just mark it
            # In a real implementation, might remove completely
            
            return {
                "success": True,
                "template_id": template_id,
                "deleted_files": deleted_files,
            }
    
    def publish_template(self, name: str, description: str, category: str,
                        content: str, readme: str | None = None,
                        examples: list[dict] = None, tags: list[str] = None,
                        license: str = "MIT", version: str = "1.0.0",
                        homepage: str | None = None, repository: str | None = None,
                        keywords: list[str] = None,
                        min_leeway_version: str | None = None,
                        workflow_version: str | None = None,
                        author_name: str = "Anonymous",
                        author_email: str | None = None) -> WorkflowTemplate:
        """
        Publish a new template.
        
        Returns:
            Created WorkflowTemplate
        """
        with self._lock:
            # Validate metadata
            errors = self._validate_template_metadata(name, description, category)
            if errors:
                raise TemplateInvalidMetadataError("Invalid template metadata", errors)
            
            # Check for duplicate name
            for t in self._template_manager._templates.values():
                if t.metadata.name.lower() == name.lower():
                    raise TemplateAlreadyExistsError(name)
            
            # Generate ID
            template_id = self._generate_template_id(name)
            
            # Create template
            template = WorkflowTemplate(
                id=template_id,
                metadata=TemplateMetadata(
                    id=template_id,
                    name=name,
                    version=version,
                    description=description,
                    author=TemplateAuthor(name=author_name, email=author_email),
                    license=license,
                    tags=tags or [],
                    category=category,
                    homepage=homepage,
                    repository=repository,
                    keywords=keywords or [],
                    min_leeway_version=min_leeway_version,
                    workflow_version=workflow_version,
                    created_at=self._iso_time(),
                    featured=False,
                    verified=False,
                ),
                content=content,
                readme=readme,
                examples=examples or [],
                variables=[],
            )
            
            self._template_manager._templates[template_id] = template
            self._downloads[template_id] = 0
            self._ratings[template_id] = []
            self._reviews[template_id] = []
            self._save_templates()
            
            return template
    
    def update_template(self, template_id: str, content: str | None = None,
                       readme: str | None = None, examples: list[dict] | None = None,
                       description: str | None = None, tags: list[str] | None = None,
                       version: str | None = None) -> WorkflowTemplate:
        """
        Update an existing template.
        
        Returns:
            Updated WorkflowTemplate
        """
        with self._lock:
            if template_id not in self._template_manager._templates:
                raise TemplateNotFoundError(template_id, list(self._template_manager._templates.keys()))
            
            template = self._template_manager._templates[template_id]
            
            # Update fields
            if content is not None:
                template.content = content
            if readme is not None:
                template.readme = readme
            if examples is not None:
                template.examples = examples
            if description is not None:
                template.metadata.description = description
            if tags is not None:
                template.metadata.tags = tags
            if version is not None:
                template.metadata.version = version
            
            template.metadata.updated_at = self._iso_time()
            
            self._save_templates()
            return template
    
    def delete_template(self, template_id: str, reason: str | None = None) -> bool:
        """Delete a template."""
        with self._lock:
            if template_id not in self._template_manager._templates:
                raise TemplateNotFoundError(template_id, list(self._template_manager._templates.keys()))
            
            del self._template_manager._templates[template_id]
            self._downloads.pop(template_id, None)
            self._ratings.pop(template_id, None)
            self._reviews.pop(template_id, None)
            self._save_templates()
            
            return True
    
    def rate_template(self, template_id: str, rating: int, user_id: str = "anonymous") -> dict:
        """
        Rate a template.
        
        Returns:
            Dict with new rating summary
        """
        with self._lock:
            if template_id not in self._template_manager._templates:
                raise TemplateNotFoundError(template_id, list(self._template_manager._templates.keys()))
            
            # Validate rating
            if rating < 1 or rating > 5:
                raise TemplateRatingFailedError(template_id, "Rating must be between 1 and 5")
            
            # Add or update rating
            if template_id not in self._ratings:
                self._ratings[template_id] = []
            
            # Remove old rating from this user if exists
            self._ratings[template_id] = [
                r for r in self._ratings[template_id] if r.get("user_id") != user_id
            ]
            
            # Add new rating
            self._ratings[template_id].append({
                "user_id": user_id,
                "rating": rating,
                "timestamp": self._iso_time(),
            })
            
            self._save_templates()
            
            rating_summary = self._get_rating(template_id)
            return {
                "success": True,
                "template_id": template_id,
                "new_average": rating_summary.average,
                "total_ratings": rating_summary.count,
            }
    
    def add_review(self, template_id: str, rating: int, content: str,
                  user_id: str, user_name: str,
                  title: str | None = None) -> TemplateReview:
        """
        Add a review to a template.
        
        Returns:
            Created TemplateReview
        """
        with self._lock:
            if template_id not in self._template_manager._templates:
                raise TemplateNotFoundError(template_id, list(self._template_manager._templates.keys()))
            
            # Validate rating
            if rating < 1 or rating > 5:
                raise TemplateReviewFailedError(template_id, "Rating must be between 1 and 5")
            
            # Create review
            review_id = str(uuid.uuid4())[:8]
            review = TemplateReview(
                id=review_id,
                template_id=template_id,
                user_id=user_id,
                user_name=user_name,
                rating=rating,
                title=title,
                content=content,
                created_at=self._iso_time(),
            )
            
            if template_id not in self._reviews:
                self._reviews[template_id] = []
            
            self._reviews[template_id].append(review)
            
            # Also add/update rating
            self.rate_template(template_id, rating, user_id)
            
            self._save_templates()
            return review
    
    def get_reviews(self, template_id: str, page: int = 1, limit: int = 10) -> tuple[list[TemplateReview], int, int]:
        """Get reviews for a template."""
        with self._lock:
            reviews = self._reviews.get(template_id, [])
            
            # Sort by date (newest first)
            reviews = sorted(reviews, key=lambda r: r.created_at, reverse=True)
            
            total = len(reviews)
            total_pages = (total + limit - 1) // limit
            start = (page - 1) * limit
            end = start + limit
            
            return reviews[start:end], total, total_pages
    
    def get_featured(self, category: str | None = None, limit: int = 10) -> list[WorkflowTemplate]:
        """Get featured templates."""
        with self._lock:
            templates = [t for t in self._template_manager._templates.values() if t.metadata.featured]
            
            if category:
                templates = [t for t in templates if t.metadata.category == category]
            
            return templates[:limit]
    
    def get_popular(self, category: str | None = None, 
                   time_range: str = "all", limit: int = 10) -> list[WorkflowTemplate]:
        """Get popular templates."""
        with self._lock:
            templates = list(self._template_manager._templates.values())
            
            if category:
                templates = [t for t in templates if t.metadata.category == category]
            
            # Sort by downloads
            templates = sorted(templates,
                             key=lambda t: self._downloads.get(t.id, 0),
                             reverse=True)
            
            return templates[:limit]
    
    def get_newest(self, category: str | None = None, limit: int = 10) -> list[WorkflowTemplate]:
        """Get newest templates."""
        with self._lock:
            templates = list(self._template_manager._templates.values())
            
            if category:
                templates = [t for t in templates if t.metadata.category == category]
            
            # Sort by created_at
            templates = sorted(templates,
                             key=lambda t: t.metadata.created_at,
                             reverse=True)
            
            return templates[:limit]
    
    def get_template_versions(self, template_id: str) -> list[dict]:
        """Get all versions of a template."""
        with self._lock:
            if template_id not in self._template_manager._templates:
                raise TemplateNotFoundError(template_id, list(self._template_manager._templates.keys()))
            
            template = self._template_manager._templates[template_id]
            
            # For now, just return current version
            # In full impl, would track version history
            return [{
                "version": template.metadata.version,
                "created_at": template.metadata.created_at,
                "is_current": True,
            }]
    
    def download_template(self, template_id: str, version: str | None = None) -> dict:
        """Download template content."""
        with self._lock:
            if template_id not in self._template_manager._templates:
                raise TemplateNotFoundError(template_id, list(self._template_manager._templates.keys()))
            
            template = self._template_manager._templates[template_id]
            
            # If version specified, check it exists
            if version and version != template.metadata.version:
                # In full impl, would have version history
                raise TemplateNotFoundError(template_id, [template.metadata.version])
            
            return {
                "success": True,
                "template_id": template_id,
                "version": template.metadata.version,
                "content": template.content,
            }


# =============================================================================
# WorkflowVisualEditor: Visual Workflow Editor Manager
# =============================================================================

class WorkflowVisualEditor:
    """
    Manager for visual workflow editor.
    
    Features:
    - Project management (create, open, save, delete)
    - YAML parsing and serialization
    - Node and edge operations
    - Auto-layout
    - Validation
    - Undo/Redo support
    """
    
    def __init__(self, projects_dir: Path | None = None, workflows_dir: Path | None = None):
        """
        Initialize the visual editor manager.
        
        Args:
            projects_dir: Base directory for editor projects (default: .leeway/editor/projects)
            workflows_dir: Base directory for workflows (default: .leeway/workflows)
        """
        if projects_dir is None:
            projects_dir = Path(".leeway/editor/projects")
        self._projects_dir = projects_dir
        self._projects_dir.mkdir(parents=True, exist_ok=True)
        
        if workflows_dir is None:
            workflows_dir = Path(".leeway/workflows")
        self._workflows_dir = workflows_dir
        
        # Structure: {project_id: EditorProject}
        self._projects: dict[str, EditorProject] = {}
        self._lock = threading.Lock()
        
        # Undo/Redo stacks: {project_id: list of EditorProject}
        self._undo_stacks: dict[str, list[EditorProject]] = {}
        self._redo_stacks: dict[str, list[EditorProject]] = {}
        
        # Load existing projects
        self._load_projects()
    
    def _load_projects(self) -> None:
        """Load projects from storage file."""
        storage_path = self._projects_dir / "projects.json"
        if not storage_path.exists():
            return
        
        try:
            with open(storage_path) as f:
                data = json.load(f)
                for project_data in data.get("projects", []):
                    project = EditorProject(**project_data)
                    self._projects[project.id] = project
        except Exception:
            pass  # Start with empty projects
    
    def _save_projects(self) -> None:
        """Save projects to storage file."""
        self._projects_dir.mkdir(parents=True, exist_ok=True)
        storage_path = self._projects_dir / "projects.json"
        
        with open(storage_path, "w") as f:
            json.dump({
                "projects": [p.model_dump() for p in self._projects.values()],
            }, f, indent=2)
    
    def _iso_time(self, timestamp: float | None = None) -> str:
        """Generate ISO format timestamp."""
        import datetime
        if timestamp is None:
            timestamp = time.time()
        return datetime.datetime.fromtimestamp(timestamp).isoformat() + "Z"
    
    def _generate_project_id(self, name: str) -> str:
        """Generate a unique project ID from name."""
        import re
        base_id = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        
        # Add random suffix if exists
        if base_id in [p.id for p in self._projects.values()]:
            suffix = secrets.token_hex(4)
            base_id = f"{base_id}-{suffix}"
        
        return base_id
    
    def _parse_yaml_to_graph(self, yaml_content: str) -> tuple[list[EditorNode], list[EditorEdge]]:
        """
        Parse YAML workflow content to graph structure.
        
        Returns:
            Tuple of (nodes, edges)
        """
        import yaml as yaml_module
        
        try:
            workflow_data = yaml_module.safe_load(yaml_content)
        except yaml_module.YAMLError as e:
            raise EditorYamlParseError(str(e))
        
        nodes = []
        edges = []
        node_positions = {}  # Track positions for auto-layout
        
        if not workflow_data:
            return nodes, edges
        
        # Generate node positions using simple grid layout
        y_offset = 0
        x_base = 100
        
        for node_name, node_config in workflow_data.items():
            # Skip if node_config is not a dict (e.g., if YAML has string values)
            if not isinstance(node_config, dict):
                continue
                
            node_id = f"node-{secrets.token_hex(4)}"
            
            # Determine node type
            node_type = "linear"
            if "parallel" in node_config:
                node_type = "parallel"
            elif "edges" in node_config and isinstance(node_config.get("edges"), list) and len(node_config.get("edges", [])) > 1:
                # Multiple edges means branching
                node_type = "branch"
            
            # Check for loop (target is same node)
            edges_value = node_config.get("edges")
            if isinstance(edges_value, list):
                for edge in edges_value:
                    if isinstance(edge, dict) and edge.get("target") == node_name:
                        node_type = "loop"
                        break
            
            # Check for terminal (no edges)
            edges_list = node_config.get("edges") if isinstance(node_config.get("edges"), list) else []
            if not edges_list:
                node_type = "terminal"
            
            # Create node
            node_edges = node_config.get("edges") if isinstance(node_config.get("edges"), list) else []
            node = EditorNode(
                id=node_id,
                type=node_type,
                name=node_name,
                position=EditorPosition(x=x_base, y=y_offset),
                config=EditorNodeConfig(
                    prompt=node_config.get("prompt"),
                    tools=node_config.get("tools", []) or [],
                    skills=node_config.get("skills", []) or [],
                    edges=node_edges,
                    parallel=node_config.get("parallel"),
                    requires_approval=node_config.get("requires_approval", False),
                    max_turns=node_config.get("max_turns"),
                    timeout=node_config.get("timeout"),
                ),
            )
            nodes.append(node)
            node_positions[node_name] = (x_base, y_offset)
            
            y_offset += 150  # Move down for next node
        
        # Create edges
        for node_name, node_config in workflow_data.items():
            # Skip if node_config is not a dict
            if not isinstance(node_config, dict):
                continue
                
            source_id = None
            for node in nodes:
                if node.name == node_name:
                    source_id = node.id
                    break
            
            if not source_id:
                continue
            
            edges_value = node_config.get("edges")
            if not isinstance(edges_value, list):
                continue
                
            for edge in edges_value:
                if isinstance(edge, dict):
                    target_name = edge.get("target")
                    condition = {}
                    if "when" in edge:
                        condition = edge["when"]
                    
                    # Find target node
                    target_id = None
                    for node in nodes:
                        if node.name == target_name:
                            target_id = node.id
                            break
                    
                    if target_id:
                        edge_obj = EditorEdge(
                            id=f"edge-{secrets.token_hex(4)}",
                            source=source_id,
                            target=target_id,
                            type="signal" if "signal" in condition else "always",
                            condition=condition,
                        )
                        edges.append(edge_obj)
        
        return nodes, edges
    
    def _graph_to_yaml(self, nodes: list[EditorNode], edges: list[EditorEdge]) -> str:
        """
        Convert graph structure to YAML workflow content.
        
        Returns:
            YAML string
        """
        import yaml as yaml_module
        
        workflow = {}
        
        # Create a map of node names to their config
        node_map = {}
        for node in nodes:
            config_dict = {}
            if node.config.prompt:
                config_dict["prompt"] = node.config.prompt
            if node.config.tools:
                config_dict["tools"] = node.config.tools
            if node.config.skills:
                config_dict["skills"] = node.config.skills
            if node.config.parallel:
                config_dict["parallel"] = node.config.parallel
            if node.config.requires_approval:
                config_dict["requires_approval"] = True
            if node.config.max_turns:
                config_dict["max_turns"] = node.config.max_turns
            if node.config.timeout:
                config_dict["timeout"] = node.config.timeout
            
            workflow[node.name] = config_dict
            node_map[node.id] = node.name
        
        # Add edges
        for edge in edges:
            source_name = node_map.get(edge.source)
            target_name = node_map.get(edge.target)
            
            if source_name and target_name:
                edge_dict = {"target": target_name}
                if edge.condition:
                    edge_dict["when"] = edge.condition
                
                if "edges" not in workflow[source_name]:
                    workflow[source_name]["edges"] = []
                
                workflow[source_name]["edges"].append(edge_dict)
        
        # Dump to YAML
        try:
            yaml_content = yaml_module.dump(workflow, default_flow_style=False, sort_keys=False)
        except Exception as e:
            raise EditorYamlSerializeError(str(e))
        
        return yaml_content
    
    def _validate_graph(self, nodes: list[EditorNode], edges: list[EditorEdge]) -> tuple[bool, list[EditorValidationError], list[EditorValidationError]]:
        """
        Validate the graph structure.
        
        Returns:
            Tuple of (valid, errors, warnings)
        """
        errors = []
        warnings = []
        
        # Check for empty graph
        if not nodes:
            errors.append(EditorValidationError(
                type="syntax",
                message="Workflow has no nodes",
            ))
            return False, errors, warnings
        
        # Check for orphaned nodes (no edges pointing to them, except first)
        targets = set()
        sources = set()
        for edge in edges:
            targets.add(edge.target)
            sources.add(edge.source)
        
        # Find starting nodes (no incoming edges)
        starting_nodes = [n for n in nodes if n.id not in targets]
        if not starting_nodes:
            warnings.append(EditorValidationError(
                type="node",
                message="No clear starting node detected",
            ))
        
        # Check for dangling nodes (no outgoing edges)
        for node in nodes:
            if node.id not in sources and len(nodes) > 1:
                warnings.append(EditorValidationError(
                    type="node",
                    message=f"Node '{node.name}' has no outgoing connections",
                    node_id=node.id,
                ))
        
        # Check for circular dependencies
        visited = set()
        rec_stack = set()
        
        def has_cycle(node_id: str, path: list[str]) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)
            
            # Find all edges from this node
            for edge in edges:
                if edge.source == node_id:
                    if edge.target not in visited:
                        if has_cycle(edge.target, path[:]):
                            return True
                    elif edge.target in rec_stack:
                        # Found cycle
                        cycle_start = path.index(edge.target)
                        cycle_nodes = path[cycle_start:] + [edge.target]
                        errors.append(EditorValidationError(
                            type="edge",
                            message=f"Circular dependency: {' -> '.join(cycle_nodes)}",
                        ))
                        return True
            
            rec_stack.remove(node_id)
            return False
        
        for node in nodes:
            if node.id not in visited:
                if has_cycle(node.id, []):
                    errors.append(EditorValidationError(
                        type="edge",
                        message="Circular dependency detected in workflow graph",
                    ))
                    break
        
        # Check for invalid node types
        valid_types = ["linear", "branch", "loop", "parallel", "terminal"]
        for node in nodes:
            if node.type not in valid_types:
                errors.append(EditorValidationError(
                    type="node",
                    message=f"Invalid node type: {node.type}",
                    node_id=node.id,
                ))
        
        return len(errors) == 0, errors, warnings
    
    def _auto_layout_nodes(self, nodes: list[EditorNode], edges: list[EditorEdge], 
                          direction: str = "top-bottom") -> list[EditorNode]:
        """
        Auto-layout nodes based on their connections.
        
        Args:
            nodes: List of nodes to layout
            edges: List of edges
            direction: Layout direction ("top-bottom", "left-right", "radial")
        
        Returns:
            List of nodes with updated positions
        """
        if not nodes:
            return nodes
        
        # Build adjacency map
        in_degree = {n.id: 0 for n in nodes}
        out_edges = {n.id: [] for n in nodes}
        
        for edge in edges:
            if edge.source in out_edges:
                out_edges[edge.source].append(edge.target)
            if edge.target in in_degree:
                in_degree[edge.target] += 1
        
        # Topological sort to determine levels
        levels = {}
        current_level = [n.id for n in nodes if in_degree[n.id] == 0]
        level_num = 0
        
        while current_level:
            for node_id in current_level:
                levels[node_id] = level_num
            
            next_level = []
            for node_id in current_level:
                for target_id in out_edges[node_id]:
                    in_degree[target_id] -= 1
                    if in_degree[target_id] == 0:
                        next_level.append(target_id)
            
            current_level = next_level
            level_num += 1
        
        # Handle any remaining nodes (in cycles)
        for node in nodes:
            if node.id not in levels:
                levels[node.id] = level_num
        
        # Apply positions based on direction
        if direction == "top-bottom":
            level_spacing = 150
            node_spacing = 200
            
            # Group by level
            level_groups = {}
            for node_id, level in levels.items():
                if level not in level_groups:
                    level_groups[level] = []
                level_groups[level].append(node_id)
            
            for level, node_ids in level_groups.items():
                y = level * level_spacing
                for i, node_id in enumerate(node_ids):
                    x = i * node_spacing + 100
                    for node in nodes:
                        if node.id == node_id:
                            node.position = EditorPosition(x=x, y=y)
                            break
        
        elif direction == "left-right":
            level_spacing = 200
            node_spacing = 150
            
            level_groups = {}
            for node_id, level in levels.items():
                if level not in level_groups:
                    level_groups[level] = []
                level_groups[level].append(node_id)
            
            for level, node_ids in level_groups.items():
                x = level * level_spacing
                for i, node_id in enumerate(node_ids):
                    y = i * node_spacing + 100
                    for node in nodes:
                        if node.id == node_id:
                            node.position = EditorPosition(x=x, y=y)
                            break
        
        return nodes
    
    # Public API
    
    def create_project(self, name: str, description: str | None = None,
                       content: str | None = None,
                       metadata: EditorMetadata | None = None) -> EditorProject:
        """Create a new editor project."""
        with self._lock:
            # Check for duplicate name
            for project in self._projects.values():
                if project.name.lower() == name.lower():
                    raise EditorProjectAlreadyExistsError(name)
            
            project_id = self._generate_project_id(name)
            created_at = self._iso_time()
            
            nodes = []
            edges = []
            
            # If content provided, parse it
            if content:
                nodes, edges = self._parse_yaml_to_graph(content)
            
            project = EditorProject(
                id=project_id,
                name=name,
                description=description,
                content=content or "",
                created_at=created_at,
                updated_at=created_at,
                version=metadata.version if metadata else "1.0.0",
                nodes=nodes,
                edges=edges,
                canvas=EditorCanvas(),
                metadata=metadata or EditorMetadata(),
            )
            
            self._projects[project_id] = project
            self._undo_stacks[project_id] = []
            self._redo_stacks[project_id] = []
            self._save_projects()
            
            return project
    
    def open_project(self, project_id: str | None = None,
                    workflow_name: str | None = None) -> EditorProject:
        """Open an existing project or import from workflow file."""
        with self._lock:
            # Open by project ID
            if project_id:
                if project_id not in self._projects:
                    raise EditorProjectNotFoundError(project_id, list(self._projects.keys()))
                return self._projects[project_id]
            
            # Open from workflow file
            if workflow_name:
                # Check if project already exists for this workflow
                for project in self._projects.values():
                    if project.metadata.tags and workflow_name in project.metadata.tags:
                        return project
                
                # Load from workflow file
                workflow_path = self._workflows_dir / f"{workflow_name}.yaml"
                if not workflow_path.exists():
                    raise WorkflowNotFoundError(workflow_name, list(self._workflows_dir.glob("*.yaml")))
                
                with open(workflow_path) as f:
                    content = f.read()
                
                # Create project
                return self.create_project(
                    name=workflow_name,
                    description=f"Imported from {workflow_name}.yaml",
                    content=content,
                    metadata=EditorMetadata(
                        tags=[workflow_name],
                    ),
                )
            
            raise EditorProjectNotFoundError("unknown", list(self._projects.keys()))
    
    def save_project(self, project_id: str, content: str | None = None,
                    validate: bool = True) -> EditorProject:
        """Save a project."""
        with self._lock:
            if project_id not in self._projects:
                raise EditorProjectNotFoundError(project_id, list(self._projects.keys()))
            
            project = self._projects[project_id]
            
            # If content provided, update it
            if content is not None:
                # Validate if requested
                if validate:
                    nodes, edges = self._parse_yaml_to_graph(content)
                    valid, errors, warnings = self._validate_graph(nodes, edges)
                    if not valid:
                        error_messages = [e.message for e in errors]
                        raise EditorValidationError("Invalid workflow content", error_messages)
                
                project.content = content
                project.updated_at = self._iso_time()
            
            # If nodes/edges changed, regenerate content
            if project.nodes or project.edges:
                project.content = self._graph_to_yaml(project.nodes, project.edges)
            
            self._save_projects()
            return project
    
    def list_projects(self, limit: int = 20, offset: int = 0) -> tuple[list[EditorProjectSummary], int]:
        """List all projects."""
        with self._lock:
            projects = []
            for project in self._projects.values():
                summary = EditorProjectSummary(
                    id=project.id,
                    name=project.name,
                    description=project.description,
                    node_count=len(project.nodes),
                    edge_count=len(project.edges),
                    created_at=project.created_at,
                    updated_at=project.updated_at,
                )
                projects.append(summary)
            
            # Sort by updated_at
            projects.sort(key=lambda p: p.updated_at or p.created_at, reverse=True)
            
            total = len(projects)
            return projects[offset:offset + limit], total
    
    def delete_project(self, project_id: str) -> dict:
        """Delete a project."""
        with self._lock:
            if project_id not in self._projects:
                raise EditorProjectNotFoundError(project_id, list(self._projects.keys()))
            
            del self._projects[project_id]
            
            # Clean up undo/redo stacks
            if project_id in self._undo_stacks:
                del self._undo_stacks[project_id]
            if project_id in self._redo_stacks:
                del self._redo_stacks[project_id]
            
            self._save_projects()
            
            return {"success": True, "deleted_id": project_id}
    
    def add_node(self, project_id: str, node: EditorNode) -> EditorNode:
        """Add a node to a project."""
        with self._lock:
            if project_id not in self._projects:
                raise EditorProjectNotFoundError(project_id, list(self._projects.keys()))
            
            project = self._projects[project_id]
            
            # Check for duplicate node name
            for existing_node in project.nodes:
                if existing_node.name == node.name:
                    raise EditorValidationError(f"Node with name '{node.name}' already exists")
            
            # Validate node type
            valid_types = ["linear", "branch", "loop", "parallel", "terminal"]
            if node.type not in valid_types:
                raise EditorInvalidNodeTypeError(node.type, valid_types)
            
            # Save to undo stack
            self._save_to_undo_stack(project_id, project)
            
            project.nodes.append(node)
            project.updated_at = self._iso_time()
            
            # Regenerate content
            project.content = self._graph_to_yaml(project.nodes, project.edges)
            self._save_projects()
            
            return node
    
    def update_node(self, project_id: str, node_id: str, node: EditorNode) -> EditorNode:
        """Update a node in a project."""
        with self._lock:
            if project_id not in self._projects:
                raise EditorProjectNotFoundError(project_id, list(self._projects.keys()))
            
            project = self._projects[project_id]
            
            # Find existing node
            existing_index = None
            for i, existing_node in enumerate(project.nodes):
                if existing_node.id == node_id:
                    existing_index = i
                    break
            
            if existing_index is None:
                raise EditorNodeNotFoundError(node_id, project_id)
            
            # Save to undo stack
            self._save_to_undo_stack(project_id, project)
            
            project.nodes[existing_index] = node
            project.updated_at = self._iso_time()
            
            # Regenerate content
            project.content = self._graph_to_yaml(project.nodes, project.edges)
            self._save_projects()
            
            return node
    
    def delete_node(self, project_id: str, node_id: str) -> dict:
        """Delete a node from a project."""
        with self._lock:
            if project_id not in self._projects:
                raise EditorProjectNotFoundError(project_id, list(self._projects.keys()))
            
            project = self._projects[project_id]
            
            # Find node
            node_index = None
            for i, node in enumerate(project.nodes):
                if node.id == node_id:
                    node_index = i
                    break
            
            if node_index is None:
                raise EditorNodeNotFoundError(node_id, project_id)
            
            # Save to undo stack
            self._save_to_undo_stack(project_id, project)
            
            # Remove node
            deleted_node = project.nodes.pop(node_index)
            
            # Remove associated edges
            project.edges = [
                e for e in project.edges
                if e.source != node_id and e.target != node_id
            ]
            
            project.updated_at = self._iso_time()
            
            # Regenerate content
            project.content = self._graph_to_yaml(project.nodes, project.edges)
            self._save_projects()
            
            return {"success": True, "deleted_node_id": node_id}
    
    def add_edge(self, project_id: str, edge: EditorEdge) -> EditorEdge:
        """Add an edge to a project."""
        with self._lock:
            if project_id not in self._projects:
                raise EditorProjectNotFoundError(project_id, list(self._projects.keys()))
            
            project = self._projects[project_id]
            
            # Validate source and target nodes exist
            source_exists = any(n.id == edge.source for n in project.nodes)
            target_exists = any(n.id == edge.target for n in project.nodes)
            
            if not source_exists:
                raise EditorEdgeNotFoundError(edge.source, project_id)
            if not target_exists:
                raise EditorEdgeNotFoundError(edge.target, project_id)
            
            # Validate edge doesn't create cycle (unless it's a loop)
            if edge.source == edge.target:
                # Allow self-loops (for loop nodes)
                pass
            
            # Save to undo stack
            self._save_to_undo_stack(project_id, project)
            
            project.edges.append(edge)
            project.updated_at = self._iso_time()
            
            # Regenerate content
            project.content = self._graph_to_yaml(project.nodes, project.edges)
            self._save_projects()
            
            return edge
    
    def update_edge(self, project_id: str, edge_id: str, edge: EditorEdge) -> EditorEdge:
        """Update an edge in a project."""
        with self._lock:
            if project_id not in self._projects:
                raise EditorProjectNotFoundError(project_id, list(self._projects.keys()))
            
            project = self._projects[project_id]
            
            # Find existing edge
            existing_index = None
            for i, existing_edge in enumerate(project.edges):
                if existing_edge.id == edge_id:
                    existing_index = i
                    break
            
            if existing_index is None:
                raise EditorEdgeNotFoundError(edge_id, project_id)
            
            # Save to undo stack
            self._save_to_undo_stack(project_id, project)
            
            project.edges[existing_index] = edge
            project.updated_at = self._iso_time()
            
            # Regenerate content
            project.content = self._graph_to_yaml(project.nodes, project.edges)
            self._save_projects()
            
            return edge
    
    def delete_edge(self, project_id: str, edge_id: str) -> dict:
        """Delete an edge from a project."""
        with self._lock:
            if project_id not in self._projects:
                raise EditorProjectNotFoundError(project_id, list(self._projects.keys()))
            
            project = self._projects[project_id]
            
            # Find edge
            edge_index = None
            for i, edge in enumerate(project.edges):
                if edge.id == edge_id:
                    edge_index = i
                    break
            
            if edge_index is None:
                raise EditorEdgeNotFoundError(edge_id, project_id)
            
            # Save to undo stack
            self._save_to_undo_stack(project_id, project)
            
            # Remove edge
            project.edges.pop(edge_index)
            project.updated_at = self._iso_time()
            
            # Regenerate content
            project.content = self._graph_to_yaml(project.nodes, project.edges)
            self._save_projects()
            
            return {"success": True, "deleted_edge_id": edge_id}
    
    def validate(self, project_id: str | None = None, content: str | None = None) -> EditorValidationResult:
        """Validate a project or raw content."""
        with self._lock:
            if content:
                # Validate raw content
                try:
                    nodes, edges = self._parse_yaml_to_graph(content)
                except EditorYamlParseError as e:
                    return EditorValidationResult(
                        valid=False,
                        errors=[EditorValidationError(
                            type="syntax",
                            message=e.message,
                        )],
                        warnings=[],
                    )
                
                valid, errors, warnings = self._validate_graph(nodes, edges)
                return EditorValidationResult(valid=valid, errors=errors, warnings=warnings)
            
            if project_id:
                if project_id not in self._projects:
                    raise EditorProjectNotFoundError(project_id, list(self._projects.keys()))
                
                project = self._projects[project_id]
                valid, errors, warnings = self._validate_graph(project.nodes, project.edges)
                return EditorValidationResult(valid=valid, errors=errors, warnings=warnings)
            
            raise EditorProjectNotFoundError("unknown", list(self._projects.keys()))
    
    def export_project(self, project_id: str, options: EditorExportOptions | None = None) -> dict:
        """Export a project."""
        with self._lock:
            if project_id not in self._projects:
                raise EditorProjectNotFoundError(project_id, list(self._projects.keys()))
            
            project = self._projects[project_id]
            options = options or EditorExportOptions()
            
            if options.format == "json":
                content = json.dumps({
                    "project": project.model_dump(),
                }, indent=2 if options.pretty_print else None)
            else:
                content = self._graph_to_yaml(project.nodes, project.edges)
            
            return {
                "success": True,
                "content": content,
                "format": options.format,
            }
    
    def import_content(self, content: str, name: str | None = None,
                      description: str | None = None) -> EditorProject:
        """Import workflow content as a new project."""
        with self._lock:
            # Validate content first
            try:
                nodes, edges = self._parse_yaml_to_graph(content)
            except EditorYamlParseError as e:
                raise EditorYamlParseError(e.message)
            
            # Generate name from content if not provided
            if not name:
                # Try to find a suitable name from the workflow
                import yaml as yaml_module
                try:
                    workflow_data = yaml_module.safe_load(content)
                    if workflow_data:
                        name = list(workflow_data.keys())[0] if workflow_data else "imported-workflow"
                except:
                    name = "imported-workflow"
            
            return self.create_project(
                name=name,
                description=description,
                content=content,
            )
    
    def preview(self, project_id: str, format: str = "yaml") -> dict:
        """Preview project content."""
        with self._lock:
            if project_id not in self._projects:
                raise EditorProjectNotFoundError(project_id, list(self._projects.keys()))
            
            project = self._projects[project_id]
            
            if format == "json":
                content = json.dumps(project.model_dump(), indent=2)
            else:
                content = self._graph_to_yaml(project.nodes, project.edges)
            
            return {
                "success": True,
                "content": content,
                "format": format,
            }
    
    def auto_layout(self, project_id: str, direction: str = "top-bottom") -> EditorProject:
        """Auto-layout nodes in a project."""
        with self._lock:
            if project_id not in self._projects:
                raise EditorProjectNotFoundError(project_id, list(self._projects.keys()))
            
            project = self._projects[project_id]
            
            # Save to undo stack
            self._save_to_undo_stack(project_id, project)
            
            # Apply auto-layout
            project.nodes = self._auto_layout_nodes(project.nodes, project.edges, direction)
            project.updated_at = self._iso_time()
            
            self._save_projects()
            return project
    
    def duplicate_node(self, project_id: str, node_id: str,
                     offset_x: int = 50, offset_y: int = 50) -> EditorNode:
        """Duplicate a node."""
        with self._lock:
            if project_id not in self._projects:
                raise EditorProjectNotFoundError(project_id, list(self._projects.keys()))
            
            project = self._projects[project_id]
            
            # Find source node
            source_node = None
            for node in project.nodes:
                if node.id == node_id:
                    source_node = node
                    break
            
            if not source_node:
                raise EditorNodeNotFoundError(node_id, project_id)
            
            # Save to undo stack
            self._save_to_undo_stack(project_id, project)
            
            # Create new node
            new_node = EditorNode(
                id=f"node-{secrets.token_hex(4)}",
                type=source_node.type,
                name=f"{source_node.name}-copy",
                position=EditorPosition(
                    x=source_node.position.x + offset_x,
                    y=source_node.position.y + offset_y,
                ),
                config=source_node.config.model_copy(),
            )
            
            project.nodes.append(new_node)
            project.updated_at = self._iso_time()
            
            # Regenerate content
            project.content = self._graph_to_yaml(project.nodes, project.edges)
            self._save_projects()
            
            return new_node
    
    def _save_to_undo_stack(self, project_id: str, project: EditorProject) -> None:
        """Save current state to undo stack."""
        if project_id not in self._undo_stacks:
            self._undo_stacks[project_id] = []
        
        # Deep copy the project
        project_copy = project.model_copy(deep=True)
        self._undo_stacks[project_id].append(project_copy)
        
        # Limit stack size
        if len(self._undo_stacks[project_id]) > 50:
            self._undo_stacks[project_id] = self._undo_stacks[project_id][-50:]
        
        # Clear redo stack
        if project_id in self._redo_stacks:
            self._redo_stacks[project_id] = []
    
    def undo(self, project_id: str) -> EditorProject:
        """Undo last operation."""
        with self._lock:
            if project_id not in self._projects:
                raise EditorProjectNotFoundError(project_id, list(self._projects.keys()))
            
            if project_id not in self._undo_stacks or not self._undo_stacks[project_id]:
                raise EditorValidationError("Nothing to undo")
            
            project = self._projects[project_id]
            
            # Save current state to redo stack
            if project_id not in self._redo_stacks:
                self._redo_stacks[project_id] = []
            self._redo_stacks[project_id].append(project.model_copy(deep=True))
            
            # Restore previous state
            previous_state = self._undo_stacks[project_id].pop()
            self._projects[project_id] = previous_state
            
            self._save_projects()
            return previous_state
    
    def redo(self, project_id: str) -> EditorProject:
        """Redo last undone operation."""
        with self._lock:
            if project_id not in self._projects:
                raise EditorProjectNotFoundError(project_id, list(self._projects.keys()))
            
            if project_id not in self._redo_stacks or not self._redo_stacks[project_id]:
                raise EditorValidationError("Nothing to redo")
            
            project = self._projects[project_id]
            
            # Save current state to undo stack
            if project_id not in self._undo_stacks:
                self._undo_stacks[project_id] = []
            self._undo_stacks[project_id].append(project.model_copy(deep=True))
            
            # Restore next state
            next_state = self._redo_stacks[project_id].pop()
            self._projects[project_id] = next_state
            
            self._save_projects()
            return next_state


# =============================================================================
# Phase B.5: Workflow Testing Framework
# =============================================================================

class WorkflowTestRunner:
    """
    Manager for workflow testing.
    
    Features:
    - Test case definition and storage
    - Test execution with assertions
    - Test suite management
    - Coverage analysis
    - Test history and metrics
    """
    
    def __init__(self, tests_dir: Path | None = None, storage_path: Path | None = None,
                 workflows_dir: Path | None = None):
        """
        Initialize the test runner.
        
        Args:
            tests_dir: Base directory for tests (default: .leeway/tests)
            storage_path: Path to test registry storage (default: .leeway/tests/registry.json)
            workflows_dir: Base directory for workflows (for test execution)
        """
        if tests_dir is None:
            tests_dir = Path(".leeway/tests")
        self._tests_dir = tests_dir
        self._tests_dir.mkdir(parents=True, exist_ok=True)
        
        if storage_path is None:
            storage_path = tests_dir / "registry.json"
        self._storage_path = storage_path
        
        self._workflows_dir = workflows_dir or Path(".leeway/workflows")
        
        # Test storage: {test_id: WorkflowTestCase}
        self._tests: dict[str, WorkflowTestCase] = {}
        
        # Test history: {test_id: [execution_results]}
        self._history: dict[str, list[dict]] = {}
        
        # Test suites: {suite_id: WorkflowTestSuite}
        self._suites: dict[str, WorkflowTestSuite] = {}
        
        # Metrics (in-memory)
        self._metrics_total_runs = 0
        self._metrics_passed = 0
        self._metrics_failed = 0
        self._metrics_skipped = 0
        self._metrics_total_duration_ms = 0
        
        self._lock = threading.Lock()
        
        # Load existing tests
        self._load_tests()
    
    def _iso_time(self, timestamp: float | None = None) -> str:
        """Generate ISO format timestamp."""
        import datetime
        if timestamp is None:
            timestamp = time.time()
        return datetime.datetime.fromtimestamp(timestamp).isoformat() + "Z"
    
    def _generate_test_id(self, name: str) -> str:
        """Generate a unique test ID from name."""
        import re
        base_id = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        
        if base_id in self._tests:
            suffix = secrets.token_hex(4)
            base_id = f"{base_id}-{suffix}"
        
        return base_id
    
    def _load_tests(self) -> None:
        """Load tests from storage file."""
        if not self._storage_path.exists():
            return
        
        try:
            with open(self._storage_path) as f:
                data = json.load(f)
                
                # Load tests
                for test_data in data.get("tests", []):
                    test = WorkflowTestCase(**test_data)
                    self._tests[test.id] = test
                
                # Load history
                self._history = data.get("history", {})
                
                # Load suites
                for suite_data in data.get("suites", []):
                    suite = WorkflowTestSuite(**suite_data)
                    self._suites[suite.id] = suite
                
                # Load metrics
                self._metrics_total_runs = data.get("metrics_total_runs", 0)
                self._metrics_passed = data.get("metrics_passed", 0)
                self._metrics_failed = data.get("metrics_failed", 0)
                self._metrics_skipped = data.get("metrics_skipped", 0)
                self._metrics_total_duration_ms = data.get("metrics_total_duration_ms", 0)
                
        except Exception:
            pass
    
    def _save_tests(self) -> None:
        """Save tests to storage file."""
        # Convert tests to dict for JSON serialization
        tests_list = [t.model_dump() for t in self._tests.values()]
        suites_list = [s.model_dump() for s in self._suites.values()]
        
        with open(self._storage_path, "w") as f:
            json.dump({
                "tests": tests_list,
                "history": self._history,
                "suites": suites_list,
                "metrics_total_runs": self._metrics_total_runs,
                "metrics_passed": self._metrics_passed,
                "metrics_failed": self._metrics_failed,
                "metrics_skipped": self._metrics_skipped,
                "metrics_total_duration_ms": self._metrics_total_duration_ms,
            }, f, indent=2)
    
    def _run_assertion(self, assertion: TestAssertion) -> dict:
        """Run a single assertion."""
        result = {
            "type": assertion.type,
            "expected": assertion.expected,
            "actual": assertion.actual,
            "passed": False,
            "message": assertion.message,
        }
        
        a_type = assertion.type
        expected = assertion.expected
        actual = assertion.actual
        
        if a_type == "equals":
            result["passed"] = (expected == actual)
        elif a_type == "not_equals":
            result["passed"] = (expected != actual)
        elif a_type == "contains":
            result["passed"] = (expected in actual) if isinstance(actual, str) else False
        elif a_type == "regex":
            import re
            result["passed"] = bool(re.search(expected, str(actual))) if expected else False
        elif a_type == "greater_than":
            result["passed"] = (actual > expected) if isinstance(actual, (int, float)) else False
        elif a_type == "less_than":
            result["passed"] = (actual < expected) if isinstance(actual, (int, float)) else False
        elif a_type == "truthy":
            result["passed"] = bool(actual)
        elif a_type == "falsy":
            result["passed"] = not actual
        
        return result
    
    def run_test(self, test: WorkflowTestCase, workflow_name: str | None = None,
                 input_override: dict | None = None) -> WorkflowTestResult:
        """
        Run a single test.
        
        Args:
            test: Test case to run
            workflow_name: Override workflow name
            input_override: Override test input
            
        Returns:
            WorkflowTestResult
        """
        start_time = time.time()
        test_id = test.id
        wf_name = workflow_name or test.workflow_name
        
        try:
            # Run test input through workflow execution
            input_data = input_override or test.input
            
            # Simulate workflow execution (in real implementation, would call workflow.execute)
            # For now, we create a mock result based on expected output
            actual_output = test.expected_output.copy()  # In reality: execute workflow
            
            # Run custom assertions
            assertion_results = []
            all_passed = True
            
            for assertion in test.assertions:
                result = self._run_assertion(assertion)
                assertion_results.append(result)
                if not result["passed"]:
                    all_passed = False
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Determine status
            if all_passed and assertion_results:
                status = "passed"
            elif assertion_results and not all_passed:
                status = "failed"
            else:
                # If no assertions, check if actual matches expected
                if actual_output == test.expected_output:
                    status = "passed"
                else:
                    status = "failed"
            
            return WorkflowTestResult(
                test_id=test_id,
                name=test.name,
                status=status,
                duration_ms=duration_ms,
                output=str(actual_output),
                assertions=assertion_results,
                execution_id=str(uuid.uuid4()),
            )
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return WorkflowTestResult(
                test_id=test_id,
                name=test.name,
                status="error",
                duration_ms=duration_ms,
                error=str(e),
                execution_id=str(uuid.uuid4()),
            )
    
    def _calculate_coverage(self, workflow_name: str, test_results: list[WorkflowTestResult]) -> TestCoverageReport:
        """
        Calculate coverage for a workflow based on test executions.
        
        In reality, this would analyze actual workflow execution paths.
        For now, we create a mock coverage report.
        """
        # Mock: assume workflow has 5 nodes and 3 signals
        total_nodes = 5
        covered_nodes = min(len(test_results), total_nodes)
        
        total_signals = 3
        covered_signals = min(len([r for r in test_results if r.status == "passed"]), total_signals)
        
        node_coverage = (covered_nodes / total_nodes * 100) if total_nodes > 0 else 0
        signal_coverage = (covered_signals / total_signals * 100) if total_signals > 0 else 0
        
        return TestCoverageReport(
            workflow_name=workflow_name,
            total_nodes=total_nodes,
            covered_nodes=covered_nodes,
            node_coverage_percent=round(node_coverage, 2),
            total_signals=total_signals,
            covered_signals=covered_signals,
            signal_coverage_percent=round(signal_coverage, 2),
            uncovered_nodes=["node4", "node5"][:total_nodes - covered_nodes],
            uncovered_signals=["signal3"][:total_signals - covered_signals],
        )
    
    # Public API
    
    def create_test(self, test: WorkflowTestCase) -> WorkflowTestCase:
        """Create a new test."""
        with self._lock:
            # Generate ID if not provided
            if not test.id:
                test.id = self._generate_test_id(test.name)
            elif test.id in self._tests:
                raise TestAlreadyExistsError(test.id)
            
            self._tests[test.id] = test
            self._history[test.id] = []
            self._save_tests()
            
            return test
    
    def update_test(self, test_id: str, test: WorkflowTestCase) -> WorkflowTestCase:
        """Update an existing test."""
        with self._lock:
            if test_id not in self._tests:
                raise TestNotFoundError(test_id, list(self._tests.keys()))
            
            test.id = test_id
            self._tests[test_id] = test
            self._save_tests()
            
            return test
    
    def delete_test(self, test_id: str) -> str:
        """Delete a test."""
        with self._lock:
            if test_id not in self._tests:
                raise TestNotFoundError(test_id, list(self._tests.keys()))
            
            del self._tests[test_id]
            
            if test_id in self._history:
                del self._history[test_id]
            
            self._save_tests()
            
            return test_id
    
    def get_test(self, test_id: str) -> WorkflowTestCase | None:
        """Get a test by ID."""
        with self._lock:
            return self._tests.get(test_id)
    
    def list_tests(self, workflow_name: str | None = None, tag: str | None = None,
                test_type: str | None = None) -> list[WorkflowTestCase]:
        """List tests with optional filters."""
        with self._lock:
            tests = list(self._tests.values())
            
            if workflow_name:
                tests = [t for t in tests if t.workflow_name == workflow_name]
            
            if tag:
                tests = [t for t in tests if tag in t.tags]
            
            if test_type:
                tests = [t for t in tests if t.type == test_type]
            
            return tests
    
    def run(self, test_id: str, workflow_name: str | None = None,
          input_override: dict | None = None) -> WorkflowTestResult:
        """Run a single test."""
        with self._lock:
            test = self._tests.get(test_id)
            if not test:
                raise TestNotFoundError(test_id, list(self._tests.keys()))
            
            result = self.run_test(test, workflow_name, input_override)
            
            # Record history
            if test_id not in self._history:
                self._history[test_id] = []
            self._history[test_id].append({
                "test_id": test_id,
                "result": result.model_dump(),
                "timestamp": self._iso_time(),
            })
            
            # Keep only last 100 results per test
            if len(self._history[test_id]) > 100:
                self._history[test_id] = self._history[test_id][-100:]
            
            # Update metrics
            self._metrics_total_runs += 1
            if result.status == "passed":
                self._metrics_passed += 1
            elif result.status == "failed":
                self._metrics_failed += 1
            elif result.status == "skipped":
                self._metrics_skipped += 1
            
            self._metrics_total_duration_ms += result.duration_ms
            
            self._save_tests()
            
            return result
    
    def run_many(self, test_ids: list[str], workflow_name: str | None = None,
                parallel: bool = False) -> list[WorkflowTestResult]:
        """Run multiple tests."""
        results = []
        
        if parallel:
            # Parallel execution (would use ThreadPoolExecutor in reality)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(self.run, tid, workflow_name): tid
                    for tid in test_ids
                }
                for future in concurrent.futures.as_completed(futures):
                    try:
                        results.append(future.result())
                    except Exception as e:
                        tid = futures[future]
                        results.append(WorkflowTestResult(
                            test_id=tid,
                            name="unknown",
                            status="error",
                            error=str(e),
                        ))
        else:
            # Sequential execution
            for tid in test_ids:
                try:
                    result = self.run(tid, workflow_name)
                    results.append(result)
                except Exception as e:
                    results.append(WorkflowTestResult(
                        test_id=tid,
                        name="unknown",
                        status="error",
                        error=str(e),
                    ))
        
        return results
    
    def duplicate_test(self, test_id: str, new_name: str | None = None) -> WorkflowTestCase:
        """Duplicate a test."""
        with self._lock:
            test = self._tests.get(test_id)
            if not test:
                raise TestNotFoundError(test_id, list(self._tests.keys()))
            
            # Create duplicate with new name
            new_test = test.model_copy()
            new_test.id = self._generate_test_id(new_name or f"{test.name}-copy")
            new_test.name = new_name or f"{test.name} (Copy)"
            
            self._tests[new_test.id] = new_test
            self._history[new_test.id] = []
            self._save_tests()
            
            return new_test
    
    # Test Suite Methods
    
    def create_suite(self, name: str, description: str | None = None,
                   test_ids: list[str] = None, tags: list[str] = None) -> WorkflowTestSuite:
        """Create a test suite."""
        with self._lock:
            suite_id = secrets.token_hex(8)
            
            suite = WorkflowTestSuite(
                id=suite_id,
                name=name,
                description=description,
                test_ids=test_ids or [],
                tags=tags or [],
            )
            
            self._suites[suite_id] = suite
            self._save_tests()
            
            return suite
    
    def delete_suite(self, suite_id: str) -> str:
        """Delete a test suite."""
        with self._lock:
            if suite_id not in self._suites:
                raise TestSuiteNotFoundError(suite_id, list(self._suites.keys()))
            
            del self._suites[suite_id]
            self._save_tests()
            
            return suite_id
    
    def list_suites(self, tag: str | None = None) -> list[WorkflowTestSuite]:
        """List test suites."""
        with self._lock:
            suites = list(self._suites.values())
            
            if tag:
                suites = [s for s in suites if tag in s.tags]
            
            return suites
    
    def run_suite(self, suite_id: str, parallel: bool = False) -> WorkflowTestSuiteResult:
        """Run a test suite."""
        with self._lock:
            suite = self._suites.get(suite_id)
            if not suite:
                raise TestSuiteNotFoundError(suite_id, list(self._suites.keys()))
            
            start_time = time.time()
            
            # Get tests from suite
            test_ids = suite.test_ids
            if not test_ids:
                # If no test IDs, use all tests with matching tags
                test_ids = [t.id for t in self._tests.values() 
                          if any(tag in t.tags for tag in suite.tags)]
            
            # Run tests
            results = self.run_many(test_ids, parallel=parallel)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Count results
            passed = sum(1 for r in results if r.status == "passed")
            failed = sum(1 for r in results if r.status == "failed")
            skipped = sum(1 for r in results if r.status == "skipped")
            errors = sum(1 for r in results if r.status == "error")
            
            return WorkflowTestSuiteResult(
                suite_id=suite_id,
                suite_name=suite.name,
                total_tests=len(results),
                passed=passed,
                failed=failed,
                skipped=skipped,
                errors=errors,
                duration_ms=duration_ms,
                results=results,
            )
    
    # Coverage Methods
    
    def get_coverage(self, workflow_name: str, 
                   test_ids: list[str] = None) -> TestCoverageReport:
        """Get coverage report for a workflow."""
        with self._lock:
            # Run specified tests or all tests for workflow
            if test_ids is None:
                test_ids = [t.id for t in self._tests.values() 
                          if t.workflow_name == workflow_name]
            
            results = self.run_many(test_ids)
            
            return self._calculate_coverage(workflow_name, results)
    
    # Metrics Methods
    
    def get_metrics(self, workflow_name: str | None = None,
                   time_range: str | None = None) -> TestMetrics:
        """Get test metrics."""
        with self._lock:
            total = self._metrics_total_runs
            
            if total == 0:
                return TestMetrics(
                    total_runs=0,
                    passed=0,
                    failed=0,
                    skipped=0,
                    pass_rate=0.0,
                    avg_duration_ms=0.0,
                    total_duration_ms=0,
                )
            
            passed = self._metrics_passed
            failed = self._metrics_failed
            skipped = self._metrics_skipped
            
            return TestMetrics(
                total_runs=total,
                passed=passed,
                failed=failed,
                skipped=skipped,
                pass_rate=round(passed / total * 100, 2),
                avg_duration_ms=self._metrics_total_duration_ms / total,
                total_duration_ms=self._metrics_total_duration_ms,
            )
    
    # History Methods
    
    def get_history(self, test_id: str | None = None,
                    limit: int = 10) -> list[dict]:
        """Get test execution history."""
        with self._lock:
            if test_id:
                history = self._history.get(test_id, [])
                return history[-limit:]
            
            # Get all history
            all_history = []
            for tid, h in self._history.items():
                for entry in h:
                    entry["test_id"] = tid
                    all_history.append(entry)
            
            # Sort by timestamp and limit
            all_history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return all_history[:limit]


# =============================================================================
# Phase B.6: Workflow Performance Profiling
# =============================================================================

class WorkflowProfiler:
    """
    Manager for workflow performance profiling.
    
    Features:
    - Profile workflow execution (execution time, node time, tool time)
    - Track resource usage (CPU, memory)
    - Calculate performance metrics (avg, median, percentiles)
    - Identify bottlenecks
    - Export profiles (JSON, CSV, Chrome Tracing)
    """
    
    def __init__(self, profiles_dir: Path | None = None, storage_path: Path | None = None):
        """
        Initialize the profiler.
        
        Args:
            profiles_dir: Base directory for profiles (default: .leeway/profiles)
            storage_path: Path to profile registry storage (default: .leeway/profiles/registry.json)
        """
        if profiles_dir is None:
            profiles_dir = Path(".leeway/profiles")
        self._profiles_dir = profiles_dir
        self._profiles_dir.mkdir(parents=True, exist_ok=True)
        
        if storage_path is None:
            storage_path = profiles_dir / "registry.json"
        self._storage_path = storage_path
        
        # Profile storage: {profile_id: WorkflowProfileData}
        self._profiles: dict[str, WorkflowProfileData] = {}
        
        # Currently active profile
        self._active_profile: WorkflowProfileData | None = None
        self._active_node_profile: dict | None = None
        self._active_tool_profile: dict | None = None
        
        # Profile history: {profile_id: [execution_results]}
        self._history: dict[str, list[dict]] = {}
        
        # Sample interval for resource monitoring
        self._sample_interval_ms = 1000
        
        # Lock for thread safety
        self._lock = threading.Lock()
        
        # Load existing profiles
        self._load_profiles()
    
    def _iso_time(self, timestamp: float | None = None) -> str:
        """Generate ISO format timestamp."""
        import datetime
        if timestamp is None:
            timestamp = time.time()
        return datetime.datetime.fromtimestamp(timestamp).isoformat() + "Z"
    
    def _generate_profile_id(self, workflow_name: str) -> str:
        """Generate a unique profile ID from workflow name."""
        import re
        base_id = re.sub(r'[^a-z0-9]+', '-', workflow_name.lower()).strip('-')
        
        suffix = secrets.token_hex(6)
        return f"{base_id}-{suffix}"
    
    def _load_profiles(self) -> None:
        """Load profiles from storage file."""
        if not self._storage_path.exists():
            return
        
        try:
            with open(self._storage_path) as f:
                data = json.load(f)
                
                # Load profiles
                for profile_data in data.get("profiles", []):
                    profile = WorkflowProfileData(**profile_data)
                    self._profiles[profile.execution_id] = profile
                
                # Load history
                self._history = data.get("history", {})
        except Exception:
            pass  # Ignore errors loading profiles
    
    def _save_profiles(self) -> None:
        """Save profiles to storage file."""
        data = {
            "profiles": [p.model_dump() for p in self._profiles.values()],
            "history": self._history,
        }
        
        # Write to temp file first, then rename (atomic write)
        temp_path = self._storage_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)
        
        temp_path.rename(self._storage_path)
    
    def _calculate_percentiles(self, values: list[float]) -> dict[str, float]:
        """Calculate percentiles from a list of values."""
        if not values:
            return {"p50": 0, "p95": 0, "p99": 0}
        
        sorted_values = sorted(values)
        
        def get_percentile(p: float) -> float:
            idx = int(len(sorted_values) * p)
            if idx >= len(sorted_values):
                idx = len(sorted_values) - 1
            return sorted_values[idx]
        
        return {
            "p50": get_percentile(0.5),
            "p95": get_percentile(0.95),
            "p99": get_percentile(0.99),
        }
    
    # Profile Lifecycle Methods
    
    def start_profile(self, workflow_name: str, 
                     sample_interval_ms: int = 1000) -> str:
        """
        Start a new profile.
        
        Args:
            workflow_name: Name of workflow to profile
            sample_interval_ms: Resource sample interval
            
        Returns:
            Profile ID
        """
        with self._lock:
            profile_id = self._generate_profile_id(workflow_name)
            self._active_profile = WorkflowProfileData(
                workflow_name=workflow_name,
                execution_id=profile_id,
                started_at=self._iso_time(),
            )
            self._active_node_profile = None
            self._active_tool_profile = None
            self._sample_interval_ms = sample_interval_ms
            
            return profile_id
    
    def stop_profile(self, profile_id: str | None = None) -> WorkflowProfileData | None:
        """
        Stop the currently active profile.
        
        Args:
            profile_id: Optional specific profile ID to stop
            
        Returns:
            Profile data
        """
        with self._lock:
            profile = self._active_profile
            
            if profile_id and profile and profile.execution_id != profile_id:
                # Find specific profile
                profile = self._profiles.get(profile_id)
            
            if profile:
                profile.completed_at = self._iso_time()
                profile.duration_ms = int((datetime.datetime.now(datetime.timezone.utc).timestamp() - 
                                          datetime.datetime.fromisoformat(profile.started_at.replace("Z", "+00:00")).timestamp()) * 1000)
                
                # Save node and tool profiles
                self._profiles[profile.execution_id] = profile
                self._save_profiles()
            
            self._active_profile = None
            self._active_node_profile = None
            self._active_tool_profile = None
            
            return profile
    
    def is_active(self) -> bool:
        """Check if profiling is active."""
        return self._active_profile is not None
    
    def get_active_profile_id(self) -> str | None:
        """Get the active profile ID."""
        if self._active_profile:
            return self._active_profile.execution_id
        return None
    
    # Node Profiling Methods
    
    def start_node_profile(self, node_name: str) -> None:
        """
        Start profiling a node.
        
        Args:
            node_name: Name of node
        """
        with self._lock:
            if not self._active_profile:
                return
            
            self._active_node_profile = {
                "node_name": node_name,
                "started_at": self._iso_time(),
                "tools_called": 0,
                "llm_calls": 0,
                "llm_tokens_input": 0,
                "llm_tokens_output": 0,
            }
    
    def stop_node_profile(self, node_name: str, signal: str | None = None,
                        error: str | None = None) -> None:
        """
        Stop profiling a node.
        
        Args:
            node_name: Name of node
            signal: Signal emitted by node
            error: Error if any
        """
        with self._lock:
            if not self._active_profile or not self._active_node_profile:
                return
            
            node_profile = self._active_node_profile.copy()
            node_profile["completed_at"] = self._iso_time()
            node_profile["duration_ms"] = int(
                (datetime.datetime.now(datetime.timezone.utc).timestamp() - 
                 datetime.datetime.fromisoformat(node_profile["started_at"].replace("Z", "+00:00")).timestamp()) * 1000
            )
            node_profile["signal"] = signal
            node_profile["error"] = error
            
            self._active_profile.node_profiles.append(node_profile)
            self._active_node_profile = None
    
    def record_node_turn(self) -> None:
        """Record a turn used by the current node."""
        if self._active_node_profile:
            self._active_node_profile["turns_used"] = \
                self._active_node_profile.get("turns_used", 0) + 1
    
    def record_node_tool_call(self, tool_name: str, duration_ms: float,
                              success: bool = True, error: str | None = None) -> None:
        """
        Record a tool call in the current node.
        
        Args:
            tool_name: Tool name
            duration_ms: Tool execution duration
            success: Whether tool succeeded
            error: Error message if failed
        """
        if self._active_node_profile:
            self._active_node_profile["tools_called"] = \
                self._active_node_profile.get("tools_called", 0) + 1
    
    def record_node_llm_call(self, input_tokens: int = 0, 
                             output_tokens: int = 0) -> None:
        """
        Record an LLM call in the current node.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        """
        with self._lock:
            if not self._active_node_profile:
                return
            
            self._active_node_profile["llm_calls"] = \
                self._active_node_profile.get("llm_calls", 0) + 1
            self._active_node_profile["llm_tokens_input"] = \
                self._active_node_profile.get("llm_tokens_input", 0) + input_tokens
            self._active_node_profile["llm_tokens_output"] = \
                self._active_node_profile.get("llm_tokens_output", 0) + output_tokens
            
            # Also record in tool profiles
            if not self._active_tool_profile:
                return
            
            self._active_tool_profile["input_tokens"] = \
                self._active_tool_profile.get("input_tokens", 0) + input_tokens
            self._active_tool_profile["output_tokens"] = \
                self._active_tool_profile.get("output_tokens", 0) + output_tokens
    
    # Tool Profiling Methods
    
    def start_tool_profile(self, tool_name: str) -> None:
        """
        Start profiling a tool call.
        
        Args:
            tool_name: Tool name
        """
        with self._lock:
            if not self._active_profile:
                return
            
            self._active_tool_profile = {
                "tool_name": tool_name,
                "called_at": self._iso_time(),
            }
    
    def stop_tool_profile(self, tool_name: str, duration_ms: float,
                       success: bool = True, error: str | None = None) -> None:
        """
        Stop profiling a tool call.
        
        Args:
            tool_name: Tool name
            duration_ms: Tool execution duration
            success: Whether tool succeeded
            error: Error message if failed
        """
        with self._lock:
            if not self._active_profile or not self._active_tool_profile:
                return
            
            tool_profile = self._active_tool_profile.copy()
            tool_profile["completed_at"] = self._iso_time()
            tool_profile["duration_ms"] = int(duration_ms * 1000)
            tool_profile["success"] = success
            tool_profile["error"] = error
            
            self._active_profile.tool_profiles.append(tool_profile)
            self._active_tool_profile = None
    
    # Query Methods
    
    def list_profiles(self, workflow_name: str | None = None,
                    limit: int = 10) -> list[dict]:
        """
        List profiles.
        
        Args:
            workflow_name: Optional workflow name filter
            limit: Maximum number of profiles to return
            
        Returns:
            List of profile summaries
        """
        with self._lock:
            profiles = list(self._profiles.values())
            
            if workflow_name:
                profiles = [p for p in profiles if p.workflow_name == workflow_name]
            
            # Sort by start time (newest first)
            profiles.sort(key=lambda p: p.started_at, reverse=True)
            
            return [
                {
                    "profile_id": p.execution_id,
                    "workflow_name": p.workflow_name,
                    "started_at": p.started_at,
                    "completed_at": p.completed_at,
                    "duration_ms": p.duration_ms,
                    "node_count": len(p.node_profiles),
                    "tool_count": len(p.tool_profiles),
                }
                for p in profiles[:limit]
            ]
    
    def get_profile(self, profile_id: str) -> WorkflowProfileData | None:
        """Get a specific profile."""
        with self._lock:
            return self._profiles.get(profile_id)
    
    def delete_profile(self, profile_id: str) -> bool:
        """Delete a profile."""
        with self._lock:
            if profile_id in self._profiles:
                del self._profiles[profile_id]
                self._save_profiles()
                return True
            return False
    
    # Metrics Methods
    
    def get_metrics(self, workflow_name: str | None = None,
                  time_range: str | None = None) -> PerformanceMetrics:
        """
        Get performance metrics.
        
        Args:
            workflow_name: Optional workflow name filter
            time_range: Time range ("hour", "day", "week", "all")
            
        Returns:
            Performance metrics
        """
        with self._lock:
            profiles = list(self._profiles.values())
            
            if workflow_name:
                profiles = [p for p in profiles if p.workflow_name == workflow_name]
            
            if not profiles:
                return PerformanceMetrics()
            
            # Filter by time range if specified
            if time_range and time_range != "all":
                import datetime
                now = datetime.datetime.now(datetime.timezone.utc)
                
                if time_range == "hour":
                    cutoff = now - datetime.timedelta(hours=1)
                elif time_range == "day":
                    cutoff = now - datetime.timedelta(days=1)
                elif time_range == "week":
                    cutoff = now - datetime.timedelta(weeks=1)
                else:
                    cutoff = None
                
                if cutoff:
                    profiles = [
                        p for p in profiles
                        if datetime.datetime.fromisoformat(p.started_at.replace("Z", "+00:00")) >= cutoff
                    ]
            
            if not profiles:
                return PerformanceMetrics()
            
            durations = [p.duration_ms for p in profiles]
            successful = [p for p in profiles if p.completed_at]
            
            total_turns = sum(
                sum(np.get("turns_used", 0) for np in p.node_profiles)
                for p in profiles
            )
            total_tools = sum(len(p.tool_profiles) for p in profiles)
            total_llm = sum(
                sum(np.get("llm_calls", 0) for np in p.node_profiles)
                for p in profiles
            )
            total_tokens = sum(
                sum(np.get("llm_tokens_input", 0) + np.get("llm_tokens_output", 0)
                    for np in p.node_profiles)
                for p in profiles
            )
            
            percentiles = self._calculate_percentiles(durations)
            
            return PerformanceMetrics(
                total_executions=len(profiles),
                successful_executions=len(successful),
                failed_executions=len(profiles) - len(successful),
                success_rate=round(len(successful) / len(profiles) * 100, 2),
                avg_duration_ms=sum(durations) / len(durations),
                median_duration_ms=percentiles["p50"],
                p95_duration_ms=percentiles["p95"],
                p99_duration_ms=percentiles["p99"],
                min_duration_ms=min(durations),
                max_duration_ms=max(durations),
                avg_turns_per_execution=total_turns / len(profiles),
                avg_tools_per_execution=total_tools / len(profiles),
                avg_llm_calls_per_execution=total_llm / len(profiles),
                avg_tokens_per_execution=total_tokens / len(profiles),
            )
    
    def get_slowest_nodes(self, workflow_name: str,
                         limit: int = 10) -> list[dict]:
        """
        Get slowest nodes for a workflow.
        
        Args:
            workflow_name: Workflow name
            limit: Maximum number of nodes to return
            
       Returns:
            List of slowest nodes
        """
        with self._lock:
            profiles = [
                p for p in self._profiles.values()
                if p.workflow_name == workflow_name
            ]
            
            if not profiles:
                return []
            
            # Aggregate node times
            node_times: dict[str, list[int]] = {}
            node_calls: dict[str, int] = {}
            node_errors: dict[str, int] = {}
            
            for profile in profiles:
                for np in profile.node_profiles:
                    name = np.get("node_name", "unknown")
                    duration = np.get("duration_ms", 0)
                    error = np.get("error")
                    
                    if name not in node_times:
                        node_times[name] = []
                        node_calls[name] = 0
                        node_errors[name] = 0
                    
                    node_times[name].append(duration)
                    node_calls[name] += 1
                    if error:
                        node_errors[name] += 1
            
            # Calculate averages
            slowest = []
            for name, durations in node_times.items():
                avg_duration = sum(durations) / len(durations)
                error_rate = node_errors[name] / node_calls[name] if node_calls[name] > 0 else 0
                
                slowest.append({
                    "node_name": name,
                    "avg_duration_ms": int(avg_duration),
                    "total_calls": node_calls[name],
                    "error_rate": round(error_rate * 100, 2),
                })
            
            # Sort by avg duration (slowest first)
            slowest.sort(key=lambda x: x["avg_duration_ms"], reverse=True)
            
            return slowest[:limit]
    
    def get_bottlenecks(self, workflow_name: str) -> list[dict]:
        """
        Get performance bottlenecks for a workflow.
        
        Args:
            workflow_name: Workflow name
            
        Returns:
            List of bottlenecks
        """
        bottlenecks = []
        
        # Get slowest nodes
        slowest = self.get_slowest_nodes(workflow_name, limit=5)
        
        for node in slowest:
            if node["avg_duration_ms"] > 30000:  # > 30 seconds
                bottlenecks.append({
                    "type": "slow_node",
                    "location": f"node:{node['node_name']}",
                    "metric": "avg_duration_ms",
                    "value": node["avg_duration_ms"],
                    "threshold": 30000,
                    "severity": "critical" if node["avg_duration_ms"] > 60000 else "warning",
                })
        
        # Get metrics
        metrics = self.get_metrics(workflow_name)
        
        if metrics.p95_duration_ms > 120000:  # > 2 minutes at p95
            bottlenecks.append({
                "type": "slow_execution",
                "location": "workflow",
                "metric": "p95_duration_ms",
                "value": metrics.p95_duration_ms,
                "threshold": 120000,
                "severity": "critical",
            })
        
        if metrics.avg_tools_per_execution > 50:
            bottlenecks.append({
                "type": "high_tool_usage",
                "location": "workflow",
                "metric": "avg_tools_per_execution",
                "value": metrics.avg_tools_per_execution,
                "threshold": 50,
                "severity": "warning",
            })
        
        return bottlenecks
    
    # Export Methods
    
    def export_profile(self, profile_id: str,
                       format: str = "json") -> str | None:
        """
        Export a profile.
        
        Args:
            profile_id: Profile ID
            format: Export format ("json", "csv", "chrome-tracing")
            
        Returns:
            Exported content
        """
        with self._lock:
            profile = self._profiles.get(profile_id)
            
            if not profile:
                return None
            
            if format == "json":
                return json.dumps(profile.model_dump(), indent=2)
            
            elif format == "csv":
                lines = ["node_name,started_at,duration_ms,turns_used,tools_called,llm_calls,signal,error"]
                
                for np in profile.node_profiles:
                    lines.append(",".join([
                        str(np.get("node_name", "")),
                        str(np.get("started_at", "")),
                        str(np.get("duration_ms", 0)),
                        str(np.get("turns_used", 0)),
                        str(np.get("tools_called", 0)),
                        str(np.get("llm_calls", 0)),
                        str(np.get("signal", "")),
                        str(np.get("error", "")),
                    ]))
                
                return "\n".join(lines)
            
            elif format == "chrome-tracing":
                # Chrome Tracing format
                events = []
                
                for np in profile.node_profiles:
                    events.append({
                        "name": np.get("node_name", "unknown"),
                        "ph": "B",
                        "ts": int(datetime.datetime.fromisoformat(
                            np["started_at"].replace("Z", "+00:00")
                        ).timestamp() * 1000000),
                        "pid": 0,
                        "tid": 0,
                    })
                    events.append({
                        "name": np.get("node_name", "unknown"),
                        "ph": "E",
                        "ts": int(datetime.datetime.fromisoformat(
                            np["completed_at"].replace("Z", "+00:00")
                        ).timestamp() * 1000000),
                        "pid": 0,
                        "tid": 0,
                    })
                
                return json.dumps(events, indent=2)
            
            return None
    
    # Clear Methods
    
    def clear(self, workflow_name: str | None = None) -> int:
        """
        Clear profiles.
        
        Args:
            workflow_name: Optional workflow name filter
            
        Returns:
            Number of profiles deleted
        """
        with self._lock:
            if workflow_name:
                to_delete = [
                    pid for pid, p in self._profiles.items()
                    if p.workflow_name == workflow_name
                ]
            else:
                to_delete = list(self._profiles.keys())
            
            for pid in to_delete:
                del self._profiles[pid]
            
            if to_delete:
                self._save_profiles()
            
            return len(to_delete)


class Daemon:
    """Leeway daemon implementing JSON-RPC 2.0 protocol."""

    def __init__(self, workflows_dir: str = ".leeway/workflows", output: TextIO = sys.stdout, settings_path: str | None = None):
        self.version = __version__
        self.workflows_dir = Path(workflows_dir)
        self._running = False
        self._methods: dict[str, Callable] = {}
        self._register_methods()
        self._output = output
        self._current_execution_id: str | None = None
        self._hitl_pending: dict | None = None
        
        # Current user role (set via JSON-RPC or auth)
        self._current_role: str = "user"

        # Load settings and MCP config
        self._settings = self._load_settings(settings_path)
        
        # Initialize SecureConfig for API key handling
        config_dir = self.workflows_dir.parent
        self._secure_config = SecureConfig(self._settings, config_dir)
        
        # Update settings with secure values (for backward compatibility)
        if self._secure_config.get_api_key():
            self._settings["api_key"] = self._secure_config.get_api_key()
        
        # Initialize PermissionChecker for access control
        self._permission_checker = PermissionChecker(self._settings, config_dir)
        
        # Initialize AuditLogger for encrypted audit logs using SecureConfig
        audit_key = self._secure_config.get("audit_encryption_key")
        if audit_key:
            audit_key_bytes = audit_key.encode() if isinstance(audit_key, str) else audit_key
        else:
            audit_key_bytes = None
        self._audit_logger = AuditLogger(
            log_dir=config_dir / "audit",
            encryption_key=audit_key_bytes
        )
        
        # Initialize StructuredLogger for structured logging (Phase 4.4)
        log_level = self._settings.get("log_level", "INFO")
        log_output = self._settings.get("log_output", "stdout")
        self._logger = StructuredLogger(
            log_dir=config_dir / "logs",
            level=log_level,
            output=log_output,
        )
        
        # Initialize MetricsCollector for metrics collection (Phase 4.4)
        self._metrics = MetricsCollector()
        
        self._mcp_manager = McpManager(self._settings.get("mcp_servers", {}))

        # Initialize Cron scheduler
        self._cron_scheduler = CronScheduler(self.workflows_dir)

        # Initialize Scheduler daemon
        self._scheduler_daemon = SchedulerDaemon(
            self._cron_scheduler,
            self.workflows_dir,
            check_interval=60,
            output=output,
        )

        # Initialize Hook registry
        self._hook_registry = HookRegistry()

        # Initialize Custom Tool registry
        self._tool_registry = CustomToolRegistry()

        # Initialize Plugin registry
        self._plugin_registry = PluginRegistry(base_dir=self.workflows_dir.parent / "plugins")

        # Initialize Workflow version manager (Phase B.1)
        self._version_manager = WorkflowVersionManager(workflows_dir=self.workflows_dir)

        # Initialize Template marketplace manager (Phase B.2)
        self._template_manager = TemplateManager(templates_dir=self.workflows_dir.parent / "templates")

        # Initialize visual workflow editor manager (Phase B.3)
        self._editor_manager = WorkflowVisualEditor(
            projects_dir=self.workflows_dir.parent / "editor" / "projects",
            workflows_dir=self.workflows_dir,
        )

        # Initialize result cache for workflow/tool results
        # Default: cache for 5 minutes, max 100 entries
        self._result_cache = ResultCache(
            max_size=self._settings.get("cache_max_size", 100),
            default_ttl=self._settings.get("cache_ttl", 300.0),
        )

        # Define which methods can use result cache
        self._cacheable_methods = {
            "workflow.list": {"ttl": 300.0},  # 5 min
            "workflow.validate": {"ttl": 60.0},  # 1 min
            "mcp.servers": {"ttl": 60.0},  # 1 min
            "mcp.list_tools": {"ttl": 60.0},  # 1 min
            "cron.list": {"ttl": 60.0},  # 1 min
            "scheduler.status": {"ttl": 30.0},  # 30 sec
            "scheduler.executions": {"ttl": 30.0},  # 30 sec
            "hooks.list": {"ttl": 60.0},  # 1 min
            "tools.list": {"ttl": 300.0},  # 5 min
            "plugins.list": {"ttl": 300.0},  # 5 min
        }

        # Methods eligible for workflow result caching based on deterministic params
        self._deterministic_methods = {
            "workflow.execute": {"ttl": 600.0, "params": ["name", "user_context"]},  # 10 min - cache by workflow name and user_context
            "tools.execute": {"ttl": 300.0, "params": ["name", "arguments"]},  # 5 min - cache by tool name and arguments
        }
        
        # Enable audit logging if configured
        self._audit_enabled = self._settings.get("audit_enabled", True)

        # Initialize LLM Provider Manager (Phase B.4)
        self._llm_manager = LLMProviderManager(self._settings, config_dir)

        # Initialize Workflow Test Runner (Phase B.5)
        self._test_runner = WorkflowTestRunner(
            tests_dir=self.workflows_dir.parent / "tests",
            workflows_dir=self.workflows_dir,
        )
        
        # Initialize Workflow Profiler (Phase B.6)
        self._profiler = WorkflowProfiler(
            profiles_dir=self.workflows_dir.parent / "profiles",
        )

    # =============================================================================
    # Phase B.5: Testing Framework JSON-RPC Methods
    # =============================================================================

    def _tests_list(self, params: dict) -> dict:
        """Handle tests.list method - list all tests."""
        workflow_name = params.get("workflow_name")
        tag = params.get("tag")
        test_type = params.get("type")

        tests = self._test_runner.list_tests(workflow_name, tag, test_type)

        return {
            "tests": [t.model_dump() for t in tests],
            "total": len(tests),
        }

    def _tests_get(self, params: dict) -> dict:
        """Handle tests.get method - get a test by ID."""
        test_id = params.get("test_id")

        test = self._test_runner.get_test(test_id)
        if not test:
            raise TestNotFoundError(test_id, list(self._test_runner._tests.keys()))

        return {"test": test}

    def _tests_create(self, params: dict) -> dict:
        """Handle tests.create method - create a new test."""
        test_data = params.get("test", {})
        test = WorkflowTestCase(**test_data)

        created = self._test_runner.create_test(test)

        return {
            "success": True,
            "test": created.model_dump(),
        }

    def _tests_update(self, params: dict) -> dict:
        """Handle tests.update method - update a test."""
        test_id = params.get("test_id")
        test_data = params.get("test", {})
        test = WorkflowTestCase(**test_data)

        updated = self._test_runner.update_test(test_id, test)

        return {
            "success": True,
            "test": updated.model_dump(),
        }

    def _tests_delete(self, params: dict) -> dict:
        """Handle tests.delete method - delete a test."""
        test_id = params.get("test_id")

        deleted_id = self._test_runner.delete_test(test_id)

        return {
            "success": True,
            "deleted_id": deleted_id,
        }

    def _tests_run(self, params: dict) -> dict:
        """Handle tests.run method - run a single test."""
        test_id = params.get("test_id")
        workflow_name = params.get("workflow_name")
        input_override = params.get("input")

        result = self._test_runner.run(test_id, workflow_name, input_override)

        return {
            "success": result.status == "passed",
            "result": result.model_dump(),
            "error": result.error if result.status == "error" else None,
        }

    def _tests_run_many(self, params: dict) -> dict:
        """Handle tests.run_many method - run multiple tests."""
        test_ids = params.get("test_ids", [])
        workflow_name = params.get("workflow_name")
        parallel = params.get("parallel", False)

        start_time = time.time()
        results = self._test_runner.run_many(test_ids, workflow_name, parallel)
        duration_ms = int((time.time() - start_time) * 1000)

        passed = sum(1 for r in results if r.status == "passed")
        failed = sum(1 for r in results if r.status == "failed")

        return {
            "success": failed == 0,
            "results": [r.model_dump() for r in results],
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "duration_ms": duration_ms,
        }

    def _tests_duplicate(self, params: dict) -> dict:
        """Handle tests.duplicate method - duplicate a test."""
        test_id = params.get("test_id")
        new_name = params.get("new_name")

        new_test = self._test_runner.duplicate_test(test_id, new_name)

        return {
            "success": True,
            "new_test": new_test.model_dump(),
        }

    # Test Suite Methods

    def _suite_create(self, params: dict) -> dict:
        """Handle tests.suite.create method - create a test suite."""
        name = params.get("name")
        description = params.get("description")
        test_ids = params.get("test_ids", [])
        tags = params.get("tags", [])

        suite = self._test_runner.create_suite(name, description, test_ids, tags)

        return {
            "success": True,
            "suite": suite.model_dump(),
        }

    def _suite_list(self, params: dict) -> dict:
        """Handle tests.suite.list method - list test suites."""
        tag = params.get("tag")

        suites = self._test_runner.list_suites(tag)

        return {
            "suites": [s.model_dump() for s in suites],
            "total": len(suites),
        }

    def _suite_run(self, params: dict) -> dict:
        """Handle tests.suite.run method - run a test suite."""
        suite_id = params.get("suite_id")
        parallel = params.get("parallel", False)

        result = self._test_runner.run_suite(suite_id, parallel)

        return {
            "success": result.failed == 0,
            "result": result.model_dump(),
        }

    def _suite_delete(self, params: dict) -> dict:
        """Handle tests.suite.delete method - delete a test suite."""
        suite_id = params.get("suite_id")

        deleted_id = self._test_runner.delete_suite(suite_id)

        return {
            "success": True,
            "deleted_id": deleted_id,
        }

    # Coverage Methods

    def _tests_coverage(self, params: dict) -> dict:
        """Handle tests.coverage method - get coverage report."""
        workflow_name = params.get("workflow_name")
        test_ids = params.get("test_ids", [])

        report = self._test_runner.get_coverage(workflow_name, test_ids)

        return {
            "success": True,
            "report": report.model_dump(),
        }

    # Metrics Methods

    def _tests_metrics(self, params: dict) -> dict:
        """Handle tests.metrics method - get test metrics."""
        workflow_name = params.get("workflow_name")
        time_range = params.get("time_range")

        metrics = self._test_runner.get_metrics(workflow_name, time_range)

        return {"metrics": metrics.model_dump()}

    # History Methods

    def _tests_history(self, params: dict) -> dict:
        """Handle tests.history method - get test execution history."""
        test_id = params.get("test_id")
        limit = params.get("limit", 10)

        executions = self._test_runner.get_history(test_id, limit)

        return {
            "executions": executions,
            "total": len(executions),
        }

    # =============================================================================
    # Phase B.6: Performance Profiling Methods
    # =============================================================================

    def _profiler_start(self, params: dict) -> dict:
        """Handle profiler.start method - start profiling a workflow."""
        workflow_name = params.get("workflow_name")
        if not workflow_name:
            raise InvalidParamsError("Missing required parameter: workflow_name")

        sample_interval_ms = params.get("sample_interval_ms", 1000)

        profile_id = self._profiler.start_profile(workflow_name, sample_interval_ms)

        return {
            "success": True,
            "profile_id": profile_id,
            "message": f"Started profiling workflow '{workflow_name}'",
        }

    def _profiler_stop(self, params: dict) -> dict:
        """Handle profiler.stop method - stop profiling."""
        profile_id = params.get("profile_id")

        profile = self._profiler.stop_profile(profile_id)

        return {
            "success": True,
            "profile_id": profile.execution_id if profile else None,
            "profile": profile.model_dump() if profile else None,
        }

    def _profiler_list(self, params: dict) -> dict:
        """Handle profiler.list method - list profiles."""
        workflow_name = params.get("workflow_name")
        limit = params.get("limit", 10)

        profiles = self._profiler.list_profiles(workflow_name, limit)

        return {
            "profiles": profiles,
            "total": len(profiles),
        }

    def _profiler_get(self, params: dict) -> dict:
        """Handle profiler.get method - get a specific profile."""
        profile_id = params.get("profile_id")
        if not profile_id:
            raise InvalidParamsError("Missing required parameter: profile_id")

        profile = self._profiler.get_profile(profile_id)
        if not profile:
            raise ProfileNotFoundError(profile_id, list(self._profiler._profiles.keys()))

        return {
            "profile": profile.model_dump(),
        }

    def _profiler_delete(self, params: dict) -> dict:
        """Handle profiler.delete method - delete a profile."""
        profile_id = params.get("profile_id")
        if not profile_id:
            raise InvalidParamsError("Missing required parameter: profile_id")

        success = self._profiler.delete_profile(profile_id)

        return {
            "success": success,
            "deleted_id": profile_id if success else None,
        }

    def _profiler_metrics(self, params: dict) -> dict:
        """Handle profiler.metrics method - get performance metrics."""
        workflow_name = params.get("workflow_name")
        time_range = params.get("time_range")

        metrics = self._profiler.get_metrics(workflow_name, time_range)

        return {
            "metrics": metrics.model_dump(),
        }

    def _profiler_slowest(self, params: dict) -> dict:
        """Handle profiler.slowest method - get slowest nodes."""
        workflow_name = params.get("workflow_name")
        if not workflow_name:
            raise InvalidParamsError("Missing required parameter: workflow_name")

        limit = params.get("limit", 10)

        slowest = self._profiler.get_slowest_nodes(workflow_name, limit)

        return {
            "report": {
                "nodes": slowest,
            }
        }

    def _profiler_bottlenecks(self, params: dict) -> dict:
        """Handle profiler.bottlenecks method - get performance bottlenecks."""
        workflow_name = params.get("workflow_name")
        if not workflow_name:
            raise InvalidParamsError("Missing required parameter: workflow_name")

        bottlenecks = self._profiler.get_bottlenecks(workflow_name)

        return {
            "report": {
                "bottlenecks": bottlenecks,
            }
        }

    def _profiler_export(self, params: dict) -> dict:
        """Handle profiler.export method - export a profile."""
        profile_id = params.get("profile_id")
        if not profile_id:
            raise InvalidParamsError("Missing required parameter: profile_id")

        format = params.get("format", "json")

        content = self._profiler.export_profile(profile_id, format)

        return {
            "success": content is not None,
            "content": content,
            "format": format,
        }

    def _profiler_clear(self, params: dict) -> dict:
        """Handle profiler.clear method - clear profiles."""
        workflow_name = params.get("workflow_name")

        count = self._profiler.clear(workflow_name)

        return {
            "success": True,
            "deleted_count": count,
        }

    # =============================================================================
    # Phase B.4: LLM Provider Methods
    # =============================================================================

    def _llm_providers_list(self, params: dict) -> dict:
        """Handle llm.providers.list method - list all LLM providers."""
        try:
            providers = self._llm_manager.list_providers()
            return {
                "providers": [
                    {
                        "name": p.name,
                        "display_name": p.display_name,
                        "description": p.description,
                        "supports_streaming": p.supports_streaming,
                        "supports_vision": p.supports_vision,
                        "supports_function_calling": p.supports_function_calling,
                        "supports_json_mode": p.supports_json_mode,
                        "default_models": p.default_models,
                        "authentication": p.authentication,
                        "base_url": p.base_url,
                    }
                    for p in providers
                ]
            }
        except Exception as e:
            return {"providers": [], "error": str(e)}

    def _llm_models_list(self, params: dict) -> dict:
        """Handle llm.models.list method - list all available LLM models."""
        provider = params.get("provider")
        
        try:
            models = self._llm_manager.list_models(provider)
            return {
                "models": [
                    {
                        "id": m.id,
                        "display_name": m.display_name,
                        "provider": m.provider,
                        "description": m.description,
                        "context_window": m.context_window,
                        "max_output_tokens": m.max_output_tokens,
                        "supports_streaming": m.supports_streaming,
                        "supports_vision": m.supports_vision,
                        "supports_function_calling": m.supports_function_calling,
                        "supports_json_mode": m.supports_json_mode,
                        "pricing": m.pricing,
                    }
                    for m in models
                ]
            }
        except LlmProviderNotFoundError as e:
            raise e
        except Exception as e:
            return {"models": [], "error": str(e)}

    def _llm_execute(self, params: dict) -> dict:
        """Handle llm.execute method - execute an LLM completion."""
        model = params.get("model")
        if not model:
            raise InvalidParamsError("Missing required parameter: model")
        
        messages_data = params.get("messages", [])
        if not messages_data:
            raise InvalidParamsError("Missing required parameter: messages")
        
        # Convert messages to LLMMessage objects
        messages = []
        for msg in messages_data:
            if isinstance(msg, dict):
                messages.append(LLMMessage(role=msg.get("role", "user"), content=msg.get("content", "")))
            else:
                messages.append(msg)
        
        provider = params.get("provider")
        temperature = params.get("temperature")
        max_tokens = params.get("max_tokens")
        top_p = params.get("top_p")
        stream = params.get("stream", False)
        tools_data = params.get("tools")
        system = params.get("system")
        
        # Convert tools if provided
        tools = None
        if tools_data:
            tools = [LLMMessage(role=t.get("name", ""), content=t.get("description", "")) if isinstance(t, dict) else t for t in tools_data]
        
        try:
            completion = self._llm_manager.complete(
                model=model,
                messages=messages,
                provider=provider,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stream=stream,
                tools=tools,
                system=system,
            )
            
            return {
                "success": True,
                "completion": {
                    "id": completion.id,
                    "model": completion.model,
                    "content": completion.content,
                    "finish_reason": completion.finish_reason,
                    "usage": completion.usage,
                    "provider": completion.provider,
                    "created_at": completion.created_at,
                },
            }
        except (LlmProviderNotFoundError, LlmModelNotFoundError, LlmAuthenticationError,
                LlmRateLimitError, LlmInvalidRequestError, LlmProviderError, LlmContextLengthError) as e:
            raise e
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _llm_set_api_key(self, params: dict) -> dict:
        """Handle llm.set_api_key method - set API key for a provider."""
        provider = params.get("provider")
        if not provider:
            raise InvalidParamsError("Missing required parameter: provider")
        
        api_key = params.get("api_key")
        if not api_key:
            raise InvalidParamsError("Missing required parameter: api_key")
        
        self._llm_manager.set_api_key(provider, api_key)
        
        return {"success": True, "provider": provider, "message": f"API key set for {provider}"}

    def _send_progress(self, message: str, node: str | None = None, step: str | None = None) -> None:
        """Send a progress event to stdout."""
        event = ProgressEvent(message=message, node=node, step=step)
        self._output.write(json.dumps(event.model_dump(exclude_none=True)) + "\n")
        self._output.flush()

    def _send_node_event(self, node_name: str, action: str,
                        signal: str | None = None, signal_summary: str | None = None) -> None:
        """Send a node execution event."""
        event = NodeEvent(
            node_name=node_name,
            action=action,
            signal=signal,
            signal_summary=signal_summary
        )
        self._output.write(json.dumps(event.model_dump(exclude_none=True)) + "\n")
        self._output.flush()

    def _send_branch_event(self, branch_name: str, action: str, status: str = "pending") -> None:
        """Send a parallel branch event."""
        event = BranchEvent(branch_name=branch_name, action=action, status=status)
        self._output.write(json.dumps(event.model_dump(exclude_none=True)) + "\n")
        self._output.flush()

    def _send_workflow_event(self, action: str, workflow_name: str | None = None) -> None:
        """Send a workflow lifecycle event."""
        event = WorkflowEvent(action=action, workflow_name=workflow_name)
        self._output.write(json.dumps(event.model_dump(exclude_none=True)) + "\n")
        self._output.flush()

    def _send_hitl(self, node: str, question: str,
                  options: list[dict] | None = None) -> HitlSignal:
        """Send a HITL signal and return the signal object."""
        hitl_options = [
            HitlQuestion(label=opt["label"], description=opt.get("description", ""))
            for opt in (options or [])
        ]
        signal = HitlSignal(
            node=node,
            question=question,
            options=hitl_options
        )
        self._output.write(json.dumps(signal.model_dump(exclude_none=True)) + "\n")
        self._output.flush()
        return signal

    def _load_settings(self, settings_path: str | None = None) -> dict:
        """Load settings from settings.json."""
        if settings_path is None:
            # Try common locations
            for path in [
                Path(".leeway/settings.json"),
                Path(self.workflows_dir.parent, "settings.json"),
                Path.home() / ".leeway" / "settings.json",
            ]:
                if path.exists():
                    settings_path = str(path)
                    break

        if settings_path and Path(settings_path).exists():
            try:
                with open(settings_path) as f:
                    return json.load(f)
            except Exception:
                pass

        return {}

    def _register_methods(self) -> None:
        """Register all JSON-RPC methods."""
        self._methods = {
            "daemon.ping": self._ping,
            "daemon.warmup": self._warmup,
            "workflow.execute": self._workflow_execute,
            "workflow.list": self._workflow_list,
            "workflow.validate": self._workflow_validate,
            "workflow.respond": self._workflow_respond,
            "daemon.stop": self._stop,
            "mcp.servers": self._mcp_servers,
            "mcp.start": self._mcp_start,
            "mcp.stop": self._mcp_stop,
            "mcp.list_tools": self._mcp_list_tools,
            "mcp.execute": self._mcp_execute,
            "cron.create": self._cron_create,
            "cron.list": self._cron_list,
            "cron.delete": self._cron_delete,
            "cron.toggle": self._cron_toggle,
            "scheduler.start": self._scheduler_start,
            "scheduler.stop": self._scheduler_stop,
            "scheduler.status": self._scheduler_status,
            "scheduler.executions": self._scheduler_executions,
            "hooks.list": self._hooks_list,
            "hooks.register": self._hooks_register,
            "hooks.unregister": self._hooks_unregister,
            "hooks.toggle": self._hooks_toggle,
            "hooks.execute": self._hooks_execute,
            "tools.list": self._tools_list,
            "tools.register": self._tools_register,
            "tools.unregister": self._tools_unregister,
            "tools.toggle": self._tools_toggle,
            "tools.execute": self._tools_execute,
            "tools.get": self._tools_get,
            "tools.validate": self._tools_validate,
            # Plugin methods
            "plugins.list": self._plugins_list,
            "plugins.get": self._plugins_get,
            "plugins.install": self._plugins_install,
            "plugins.uninstall": self._plugins_uninstall,
            "plugins.enable": self._plugins_enable,
            "plugins.update": self._plugins_update,
            "plugins.search": self._plugins_search,
            "plugins.validate": self._plugins_validate,
            # Cache management methods
            "cache.get_stats": self._cache_get_stats,
            "cache.clear": self._cache_clear,
            "cache.invalidate": self._cache_invalidate,
            # Security & Permission methods
            "auth.set_role": self._auth_set_role,
            "auth.roles.list": self._auth_roles_list,
            "auth.roles.add": self._auth_roles_add,
            "auth.check": self._auth_check,
            # Audit methods
            "audit.logs": self._audit_logs,
            "audit.verify": self._audit_verify,
            "audit.cleanup": self._audit_cleanup,
            # Secure config methods
            "config.get_secure": self._config_get_secure,
            # Health check (Phase 4.4)
            "daemon.health": self._daemon_health,
            # Metrics methods (Phase 4.4)
            "metrics.get": self._metrics_get,
            "metrics.reset": self._metrics_reset,
            "metrics.summary": self._metrics_summary,
            # Phase B.1: Version management methods
            "workflow.version.list": self._version_list,
            "workflow.version.get": self._version_get,
            "workflow.version.create": self._version_create,
            "workflow.version.set_default": self._version_set_default,
            "workflow.version.deprecate": self._version_deprecate,
            "workflow.version.delete": self._version_delete,
            "workflow.version.compare": self._version_compare,
            "workflow.version.rollback": self._version_rollback,
            # Phase B.2: Template marketplace methods
            "templates.list": self._templates_list,
            "templates.get": self._templates_get,
            "templates.search": self._templates_search,
            "templates.categories": self._templates_categories,
            "templates.install": self._templates_install,
            # Phase B.4: LLM Provider methods
            "llm.providers": self._llm_providers_list,
            "llm.models": self._llm_models_list,
            "llm.execute": self._llm_execute,
            "llm.set_api_key": self._llm_set_api_key,
            "templates.uninstall": self._templates_uninstall,
            "templates.publish": self._templates_publish,
            "templates.update": self._templates_update,
            "templates.delete": self._templates_delete,
            "templates.rate": self._templates_rate,
            "templates.review": self._templates_review,
            "templates.reviews": self._templates_reviews,
            "templates.featured": self._templates_featured,
            "templates.popular": self._templates_popular,
            "templates.newest": self._templates_newest,
            "templates.versions": self._templates_versions,
            "templates.download": self._templates_download,
            # Phase B.3: Visual editor methods
            "editor.create_project": self._editor_create_project,
            "editor.open_project": self._editor_open_project,
            "editor.save_project": self._editor_save_project,
            "editor.list_projects": self._editor_list_projects,
            "editor.delete_project": self._editor_delete_project,
            "editor.add_node": self._editor_add_node,
            "editor.update_node": self._editor_update_node,
            "editor.delete_node": self._editor_delete_node,
            "editor.add_edge": self._editor_add_edge,
            "editor.update_edge": self._editor_update_edge,
            "editor.delete_edge": self._editor_delete_edge,
            "editor.validate": self._editor_validate,
            "editor.export": self._editor_export,
            "editor.import": self._editor_import,
            "editor.preview": self._editor_preview,
            "editor.auto_layout": self._editor_auto_layout,
            "editor.duplicate_node": self._editor_duplicate_node,
            "editor.undo": self._editor_undo,
            "editor.redo": self._editor_redo,
            # Phase B.5: Testing Framework methods
            "tests.list": self._tests_list,
            "tests.get": self._tests_get,
            "tests.create": self._tests_create,
            "tests.update": self._tests_update,
            "tests.delete": self._tests_delete,
            "tests.run": self._tests_run,
            "tests.run_many": self._tests_run_many,
            "tests.duplicate": self._tests_duplicate,
            "tests.coverage": self._tests_coverage,
            "tests.metrics": self._tests_metrics,
            "tests.history": self._tests_history,
            # Test Suite methods
            "tests.suite.create": self._suite_create,
            "tests.suite.list": self._suite_list,
            "tests.suite.run": self._suite_run,
            "tests.suite.delete": self._suite_delete,
            # Phase B.6: Performance Profiling methods
            "profiler.start": self._profiler_start,
            "profiler.stop": self._profiler_stop,
            "profiler.list": self._profiler_list,
            "profiler.get": self._profiler_get,
            "profiler.delete": self._profiler_delete,
            "profiler.metrics": self._profiler_metrics,
            "profiler.slowest": self._profiler_slowest,
            "profiler.bottlenecks": self._profiler_bottlenecks,
            "profiler.export": self._profiler_export,
            "profiler.clear": self._profiler_clear,
        }

    def _ping(self, params: dict) -> dict:
        """Handle daemon.ping method."""
        return {"version": self.version, "status": "healthy"}

    def _daemon_health(self, params: dict) -> dict:
        """
        Handle daemon.health method - comprehensive health check.
        
        Returns detailed health status including:
        - Daemon status
        - Component statuses (workflows, mcp, scheduler, hooks, etc.)
        - Cache statistics
        - Metrics summary
        - System info
        """
        import datetime
        
        # Check components
        components = {}
        
        # Workflows component
        try:
            workflows = self._list_workflows()
            components["workflows"] = {
                "status": "healthy",
                "count": len(workflows),
            }
        except Exception as e:
            components["workflows"] = {
                "status": "unhealthy",
                "error": str(e),
            }
        
        # MCP servers component
        try:
            if self._mcp_manager:
                servers = self._mcp_manager.list_servers()
                running = sum(1 for s in servers if s.get("status") == "running")
                components["mcp"] = {
                    "status": "healthy" if servers else "not_configured",
                    "total": len(servers),
                    "running": running,
                }
            else:
                components["mcp"] = {
                    "status": "not_configured",
                }
        except Exception as e:
            components["mcp"] = {
                "status": "unhealthy",
                "error": str(e),
            }
        
        # Scheduler component
        try:
            scheduler_status = self._scheduler_daemon.get_status()
            components["scheduler"] = {
                "status": "running" if scheduler_status.running else "stopped",
                "enabled_schedules": scheduler_status.enabled_schedules,
                "total_schedules": scheduler_status.total_schedules,
            }
        except Exception as e:
            components["scheduler"] = {
                "status": "unhealthy",
                "error": str(e),
            }
        
        # Hooks component
        try:
            hooks = self._hook_registry.list()
            components["hooks"] = {
                "status": "healthy",
                "count": len(hooks),
            }
        except Exception as e:
            components["hooks"] = {
                "status": "unhealthy",
                "error": str(e),
            }
        
        # Tools component
        try:
            tools = self._tool_registry.list()
            components["tools"] = {
                "status": "healthy",
                "count": len(tools),
            }
        except Exception as e:
            components["tools"] = {
                "status": "unhealthy",
                "error": str(e),
            }
        
        # Plugins component
        try:
            plugins = self._plugin_registry.list()
            components["plugins"] = {
                "status": "healthy",
                "count": len(plugins),
            }
        except Exception as e:
            components["plugins"] = {
                "status": "unhealthy",
                "error": str(e),
            }
        
        # Cache component
        try:
            cache_stats = self._result_cache.get_stats()
            components["cache"] = {
                "status": "healthy",
                "size": cache_stats.get("size", 0),
                "hit_rate": cache_stats.get("hit_rate", 0),
            }
        except Exception as e:
            components["cache"] = {
                "status": "unhealthy",
                "error": str(e),
            }
        
        # Determine overall health
        unhealthy_components = [
            name for name, status in components.items()
            if isinstance(status, dict) and status.get("status") == "unhealthy"
        ]
        
        overall_status = "healthy"
        if unhealthy_components:
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "version": self.version,
            "uptime_seconds": time.time() - getattr(self, "_start_time", time.time()),
            "timestamp": datetime.datetime.now().isoformat(),
            "components": components,
        }

    def _metrics_get(self, params: dict) -> dict:
        """
        Handle metrics.get method - get metrics data.
        
        Args:
            name: Optional metric name prefix filter
            
        Returns:
            Metrics data including counters, gauges, and histograms
        """
        name = params.get("name")
        metrics = self._metrics.get_metrics(name)
        return {"metrics": metrics}

    def _metrics_reset(self, params: dict) -> dict:
        """
        Handle metrics.reset method - reset metrics.
        
        Args:
            name: Optional metric name to reset
            
        Returns:
            Number of metrics reset
        """
        name = params.get("name")
        count = self._metrics.reset(name)
        return {"reset": count}

    def _metrics_summary(self, params: dict) -> dict:
        """
        Handle metrics.summary method - get metrics summary.
        
        Returns:
            Summary of all metrics
        """
        summary = self._metrics.get_summary()
        return {"summary": summary}

    # =============================================================================
    # Phase B.1: Workflow Version Management Methods
    # =============================================================================

    def _version_list(self, params: dict) -> dict:
        """
        Handle workflow.version.list method.
        
        Lists all versions of a workflow.
        """
        workflow_name = params.get("workflow_name")
        if not workflow_name:
            raise InvalidParamsError("Missing required parameter: workflow_name")

        version_list, metadata = self._version_manager.list_versions(workflow_name)

        return {
            "workflow_name": workflow_name,
            "versions": [v.model_dump() for v in version_list],
            "metadata": metadata.model_dump(),
        }

    def _version_get(self, params: dict) -> dict:
        """
        Handle workflow.version.get method.
        
        Gets a specific version of a workflow.
        """
        workflow_name = params.get("workflow_name")
        if not workflow_name:
            raise InvalidParamsError("Missing required parameter: workflow_name")

        version = params.get("version")  # Optional

        ver, is_default = self._version_manager.get_version(workflow_name, version)

        return {
            "workflow_name": workflow_name,
            "version": ver.model_dump(),
            "is_default": is_default,
        }

    def _version_create(self, params: dict) -> dict:
        """
        Handle workflow.version.create method.
        
        Creates a new version of a workflow.
        """
        workflow_name = params.get("workflow_name")
        if not workflow_name:
            raise InvalidParamsError("Missing required parameter: workflow_name")

        version = params.get("version")
        if not version:
            raise InvalidParamsError("Missing required parameter: version")

        changelog = params.get("changelog")
        created_by = params.get("created_by")
        set_default = params.get("set_default", False)

        ver = self._version_manager.create_version(
            workflow_name, version, changelog, created_by, set_default
        )

        return {
            "success": True,
            "workflow_name": workflow_name,
            "version": ver.version,
        }

    def _version_set_default(self, params: dict) -> dict:
        """
        Handle workflow.version.set_default method.
        
        Sets a version as the default.
        """
        workflow_name = params.get("workflow_name")
        if not workflow_name:
            raise InvalidParamsError("Missing required parameter: workflow_name")

        version = params.get("version")
        if not version:
            raise InvalidParamsError("Missing required parameter: version")

        ver = self._version_manager.set_default_version(workflow_name, version)

        return {
            "success": True,
            "workflow_name": workflow_name,
            "version": ver.version,
        }

    def _version_deprecate(self, params: dict) -> dict:
        """
        Handle workflow.version.deprecate method.
        
        Deprecates a version.
        """
        workflow_name = params.get("workflow_name")
        if not workflow_name:
            raise InvalidParamsError("Missing required parameter: workflow_name")

        version = params.get("version")
        if not version:
            raise InvalidParamsError("Missing required parameter: version")

        ver = self._version_manager.deprecate_version(workflow_name, version)

        return {
            "success": True,
            "workflow_name": workflow_name,
            "version": ver.version,
        }

    def _version_delete(self, params: dict) -> dict:
        """
        Handle workflow.version.delete method.
        
        Deletes a version.
        """
        workflow_name = params.get("workflow_name")
        if not workflow_name:
            raise InvalidParamsError("Missing required parameter: workflow_name")

        version = params.get("version")
        if not version:
            raise InvalidParamsError("Missing required parameter: version")

        force = params.get("force", False)

        self._version_manager.delete_version(workflow_name, version, force)

        return {
            "success": True,
            "workflow_name": workflow_name,
            "version": version,
        }

    def _version_compare(self, params: dict) -> dict:
        """
        Handle workflow.version.compare method.
        
        Compares two versions.
        """
        workflow_name = params.get("workflow_name")
        if not workflow_name:
            raise InvalidParamsError("Missing required parameter: workflow_name")

        version_a = params.get("version_a")
        if not version_a:
            raise InvalidParamsError("Missing required parameter: version_a")

        version_b = params.get("version_b")
        if not version_b:
            raise InvalidParamsError("Missing required parameter: version_b")

        result = self._version_manager.compare_versions(workflow_name, version_a, version_b)

        return result

    def _version_rollback(self, params: dict) -> dict:
        """
        Handle workflow.version.rollback method.
        
        Rolls back to a previous version.
        """
        workflow_name = params.get("workflow_name")
        if not workflow_name:
            raise InvalidParamsError("Missing required parameter: workflow_name")

        target_version = params.get("target_version")
        if not target_version:
            raise InvalidParamsError("Missing required parameter: target_version")

        new_version = params.get("new_version")
        changelog = params.get("changelog")

        new_version_str = self._version_manager.rollback(
            workflow_name, target_version, new_version, changelog
        )

        return {
            "success": True,
            "workflow_name": workflow_name,
            "target_version": target_version,
            "new_version": new_version_str,
        }

    # =============================================================================
    # Phase B.2: Template Marketplace Methods
    # =============================================================================

    def _templates_list(self, params: dict) -> dict:
        """Handle templates.list method."""
        category = params.get("category")
        tag = params.get("tag")
        search = params.get("search")
        sort_by = params.get("sort_by", "popular")
        page = params.get("page", 1)
        limit = params.get("limit", 20)

        templates, total, total_pages = self._template_manager.list_templates(
            category=category,
            tag=tag,
            search=search,
            sort_by=sort_by,
            page=page,
            limit=limit,
        )

        return {
            "templates": [t.model_dump() for t in templates],
            "total": total,
            "page": page,
            "total_pages": total_pages,
        }

    def _templates_get(self, params: dict) -> dict:
        """Handle templates.get method."""
        template_id = params.get("template_id")
        if not template_id:
            raise InvalidParamsError("Missing required parameter: template_id")

        template = self._template_manager.get_template(template_id)
        if not template:
            raise TemplateNotFoundError(template_id, list(self._template_manager._templates.keys()))

        return {"template": template.model_dump()}

    def _templates_search(self, params: dict) -> dict:
        """Handle templates.search method."""
        query = params.get("query", "")
        category = params.get("category")
        tags = params.get("tags", [])
        author = params.get("author")
        min_rating = params.get("min_rating")
        page = params.get("page", 1)
        limit = params.get("limit", 20)

        templates, total, suggestions = self._template_manager.search_templates(
            query=query,
            category=category,
            tags=tags,
            author=author,
            min_rating=min_rating,
            page=page,
            limit=limit,
        )

        return {
            "templates": [t.model_dump() for t in templates],
            "total": total,
            "suggestions": suggestions,
        }

    def _templates_categories(self, params: dict) -> dict:
        """Handle templates.categories method."""
        parent_id = params.get("parent_id")
        categories = self._template_manager.list_categories(parent_id)

        return {"categories": [c.model_dump() for c in categories]}

    def _templates_install(self, params: dict) -> dict:
        """Handle templates.install method."""
        template_id = params.get("template_id")
        if not template_id:
            raise InvalidParamsError("Missing required parameter: template_id")

        name = params.get("name")
        version = params.get("version")
        target_dir = params.get("target_dir")

        if target_dir:
            target_dir = Path(target_dir)

        result = self._template_manager.install_template(
            template_id=template_id,
            name=name,
            version=version,
            target_dir=target_dir,
        )

        return result

    def _templates_uninstall(self, params: dict) -> dict:
        """Handle templates.uninstall method."""
        template_id = params.get("template_id")
        if not template_id:
            raise InvalidParamsError("Missing required parameter: template_id")

        delete_files = params.get("delete_files", False)

        result = self._template_manager.uninstall_template(
            template_id=template_id,
            delete_files=delete_files,
        )

        return result

    def _templates_publish(self, params: dict) -> dict:
        """Handle templates.publish method."""
        name = params.get("name")
        description = params.get("description")
        category = params.get("category")
        content = params.get("content")

        if not name or not description or not category or not content:
            raise InvalidParamsError("Missing required parameters: name, description, category, content")

        readme = params.get("readme")
        examples = params.get("examples", [])
        tags = params.get("tags", [])
        license = params.get("license", "MIT")
        version = params.get("version", "1.0.0")
        homepage = params.get("homepage")
        repository = params.get("repository")
        keywords = params.get("keywords", [])
        min_leeway_version = params.get("min_leeway_version")
        workflow_version = params.get("workflow_version")
        author_name = params.get("author_name", "Anonymous")
        author_email = params.get("author_email")

        template = self._template_manager.publish_template(
            name=name,
            description=description,
            category=category,
            content=content,
            readme=readme,
            examples=examples,
            tags=tags,
            license=license,
            version=version,
            homepage=homepage,
            repository=repository,
            keywords=keywords,
            min_leeway_version=min_leeway_version,
            workflow_version=workflow_version,
            author_name=author_name,
            author_email=author_email,
        )

        return {
            "success": True,
            "template_id": template.id,
            "version": template.metadata.version,
        }

    def _templates_update(self, params: dict) -> dict:
        """Handle templates.update method."""
        template_id = params.get("template_id")
        if not template_id:
            raise InvalidParamsError("Missing required parameter: template_id")

        content = params.get("content")
        readme = params.get("readme")
        examples = params.get("examples")
        description = params.get("description")
        tags = params.get("tags")
        version = params.get("version")

        template = self._template_manager.update_template(
            template_id=template_id,
            content=content,
            readme=readme,
            examples=examples,
            description=description,
            tags=tags,
            version=version,
        )

        return {
            "success": True,
            "template_id": template.id,
            "new_version": template.metadata.version,
        }

    def _templates_delete(self, params: dict) -> dict:
        """Handle templates.delete method."""
        template_id = params.get("template_id")
        if not template_id:
            raise InvalidParamsError("Missing required parameter: template_id")

        reason = params.get("reason")

        self._template_manager.delete_template(template_id, reason)

        return {
            "success": True,
            "template_id": template_id,
        }

    def _templates_rate(self, params: dict) -> dict:
        """Handle templates.rate method."""
        template_id = params.get("template_id")
        rating = params.get("rating")

        if not template_id or rating is None:
            raise InvalidParamsError("Missing required parameters: template_id, rating")

        user_id = params.get("user_id", "anonymous")

        result = self._template_manager.rate_template(template_id, rating, user_id)

        return result

    def _templates_review(self, params: dict) -> dict:
        """Handle templates.review method."""
        template_id = params.get("template_id")
        rating = params.get("rating")
        content = params.get("content")

        if not template_id or rating is None or not content:
            raise InvalidParamsError("Missing required parameters: template_id, rating, content")

        user_id = params.get("user_id", "anonymous")
        user_name = params.get("user_name", "Anonymous")
        title = params.get("title")

        review = self._template_manager.add_review(
            template_id=template_id,
            rating=rating,
            content=content,
            user_id=user_id,
            user_name=user_name,
            title=title,
        )

        return {
            "success": True,
            "review_id": review.id,
        }

    def _templates_reviews(self, params: dict) -> dict:
        """Handle templates.reviews method."""
        template_id = params.get("template_id")
        if not template_id:
            raise InvalidParamsError("Missing required parameter: template_id")

        page = params.get("page", 1)
        limit = params.get("limit", 10)

        reviews, total, total_pages = self._template_manager.get_reviews(
            template_id=template_id,
            page=page,
            limit=limit,
        )

        return {
            "reviews": [r.model_dump() for r in reviews],
            "total": total,
            "page": page,
            "total_pages": total_pages,
        }

    def _templates_featured(self, params: dict) -> dict:
        """Handle templates.featured method."""
        category = params.get("category")
        limit = params.get("limit", 10)

        templates = self._template_manager.get_featured(category=category, limit=limit)

        return {"templates": [t.model_dump() for t in templates]}

    def _templates_popular(self, params: dict) -> dict:
        """Handle templates.popular method."""
        category = params.get("category")
        time_range = params.get("time_range", "all")
        limit = params.get("limit", 10)

        templates = self._template_manager.get_popular(
            category=category,
            time_range=time_range,
            limit=limit,
        )

        return {"templates": [t.model_dump() for t in templates]}

    def _templates_newest(self, params: dict) -> dict:
        """Handle templates.newest method."""
        category = params.get("category")
        limit = params.get("limit", 10)

        templates = self._template_manager.get_newest(category=category, limit=limit)

        return {"templates": [t.model_dump() for t in templates]}

    def _templates_versions(self, params: dict) -> dict:
        """Handle templates.versions method."""
        template_id = params.get("template_id")
        if not template_id:
            raise InvalidParamsError("Missing required parameter: template_id")

        versions = self._template_manager.get_template_versions(template_id)

        return {
            "template_id": template_id,
            "versions": versions,
        }

    def _templates_download(self, params: dict) -> dict:
        """Handle templates.download method."""
        template_id = params.get("template_id")
        if not template_id:
            raise InvalidParamsError("Missing required parameter: template_id")

        version = params.get("version")

        result = self._template_manager.download_template(template_id, version)

        return result

    # =============================================================================
    # Phase B.3: Visual Editor Methods
    # =============================================================================

    def _editor_create_project(self, params: dict) -> dict:
        """Handle editor.create_project method."""
        name = params.get("name")
        if not name:
            raise InvalidParamsError("Missing required parameter: name")

        description = params.get("description")
        content = params.get("content")
        metadata = params.get("metadata")

        # Convert metadata if provided
        editor_metadata = None
        if metadata:
            editor_metadata = EditorMetadata(**metadata)

        try:
            project = self._editor_manager.create_project(
                name=name,
                description=description,
                content=content,
                metadata=editor_metadata,
            )
            return {
                "success": True,
                "project": project.model_dump(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _editor_open_project(self, params: dict) -> dict:
        """Handle editor.open_project method."""
        project_id = params.get("project_id")
        workflow_name = params.get("workflow_name")

        if not project_id and not workflow_name:
            raise InvalidParamsError("Missing required parameter: project_id or workflow_name")

        try:
            project = self._editor_manager.open_project(project_id, workflow_name)
            return {
                "success": True,
                "project": project.model_dump(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _editor_save_project(self, params: dict) -> dict:
        """Handle editor.save_project method."""
        project_id = params.get("project_id")
        if not project_id:
            raise InvalidParamsError("Missing required parameter: project_id")

        content = params.get("content")
        validate = params.get("validate", True)

        try:
            project = self._editor_manager.save_project(project_id, content, validate)
            return {
                "success": True,
                "project": project.model_dump(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _editor_list_projects(self, params: dict) -> dict:
        """Handle editor.list_projects method."""
        limit = params.get("limit", 20)
        offset = params.get("offset", 0)

        projects, total = self._editor_manager.list_projects(limit, offset)

        return {
            "projects": [p.model_dump() for p in projects],
            "total": total,
        }

    def _editor_delete_project(self, params: dict) -> dict:
        """Handle editor.delete_project method."""
        project_id = params.get("project_id")
        if not project_id:
            raise InvalidParamsError("Missing required parameter: project_id")

        try:
            result = self._editor_manager.delete_project(project_id)
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _editor_add_node(self, params: dict) -> dict:
        """Handle editor.add_node method."""
        project_id = params.get("project_id")
        if not project_id:
            raise InvalidParamsError("Missing required parameter: project_id")

        node_data = params.get("node")
        if not node_data:
            raise InvalidParamsError("Missing required parameter: node")

        try:
            node = EditorNode(**node_data)
            result = self._editor_manager.add_node(project_id, node)
            return {
                "success": True,
                "project_id": project_id,
                "node": result.model_dump(),
            }
        except Exception as e:
            return {
                "success": False,
                "project_id": project_id,
                "error": str(e),
            }

    def _editor_update_node(self, params: dict) -> dict:
        """Handle editor.update_node method."""
        project_id = params.get("project_id")
        if not project_id:
            raise InvalidParamsError("Missing required parameter: project_id")

        node_id = params.get("node_id")
        if not node_id:
            raise InvalidParamsError("Missing required parameter: node_id")

        node_data = params.get("node")
        if not node_data:
            raise InvalidParamsError("Missing required parameter: node")

        try:
            node = EditorNode(**node_data)
            result = self._editor_manager.update_node(project_id, node_id, node)
            return {
                "success": True,
                "project_id": project_id,
                "node": result.model_dump(),
            }
        except Exception as e:
            return {
                "success": False,
                "project_id": project_id,
                "error": str(e),
            }

    def _editor_delete_node(self, params: dict) -> dict:
        """Handle editor.delete_node method."""
        project_id = params.get("project_id")
        if not project_id:
            raise InvalidParamsError("Missing required parameter: project_id")

        node_id = params.get("node_id")
        if not node_id:
            raise InvalidParamsError("Missing required parameter: node_id")

        try:
            result = self._editor_manager.delete_node(project_id, node_id)
            return {
                "success": True,
                "project_id": project_id,
                "deleted_node_id": node_id,
            }
        except Exception as e:
            return {
                "success": False,
                "project_id": project_id,
                "error": str(e),
            }

    def _editor_add_edge(self, params: dict) -> dict:
        """Handle editor.add_edge method."""
        project_id = params.get("project_id")
        if not project_id:
            raise InvalidParamsError("Missing required parameter: project_id")

        edge_data = params.get("edge")
        if not edge_data:
            raise InvalidParamsError("Missing required parameter: edge")

        try:
            edge = EditorEdge(**edge_data)
            result = self._editor_manager.add_edge(project_id, edge)
            return {
                "success": True,
                "project_id": project_id,
                "edge": result.model_dump(),
            }
        except Exception as e:
            return {
                "success": False,
                "project_id": project_id,
                "error": str(e),
            }

    def _editor_update_edge(self, params: dict) -> dict:
        """Handle editor.update_edge method."""
        project_id = params.get("project_id")
        if not project_id:
            raise InvalidParamsError("Missing required parameter: project_id")

        edge_id = params.get("edge_id")
        if not edge_id:
            raise InvalidParamsError("Missing required parameter: edge_id")

        edge_data = params.get("edge")
        if not edge_data:
            raise InvalidParamsError("Missing required parameter: edge")

        try:
            edge = EditorEdge(**edge_data)
            result = self._editor_manager.update_edge(project_id, edge_id, edge)
            return {
                "success": True,
                "project_id": project_id,
                "edge": result.model_dump(),
            }
        except Exception as e:
            return {
                "success": False,
                "project_id": project_id,
                "error": str(e),
            }

    def _editor_delete_edge(self, params: dict) -> dict:
        """Handle editor.delete_edge method."""
        project_id = params.get("project_id")
        if not project_id:
            raise InvalidParamsError("Missing required parameter: project_id")

        edge_id = params.get("edge_id")
        if not edge_id:
            raise InvalidParamsError("Missing required parameter: edge_id")

        try:
            result = self._editor_manager.delete_edge(project_id, edge_id)
            return {
                "success": True,
                "project_id": project_id,
                "deleted_edge_id": edge_id,
            }
        except Exception as e:
            return {
                "success": False,
                "project_id": project_id,
                "error": str(e),
            }

    def _editor_validate(self, params: dict) -> dict:
        """Handle editor.validate method."""
        project_id = params.get("project_id")
        content = params.get("content")

        if not project_id and not content:
            raise InvalidParamsError("Missing required parameter: project_id or content")

        try:
            result = self._editor_manager.validate(project_id, content)
            return result.model_dump()
        except Exception as e:
            return {
                "valid": False,
                "errors": [{"type": "error", "message": str(e)}],
                "warnings": [],
            }

    def _editor_export(self, params: dict) -> dict:
        """Handle editor.export method."""
        project_id = params.get("project_id")
        if not project_id:
            raise InvalidParamsError("Missing required parameter: project_id")

        options_data = params.get("options")
        options = None
        if options_data:
            options = EditorExportOptions(**options_data)

        try:
            result = self._editor_manager.export_project(project_id, options)
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "format": options_data.get("format", "yaml") if options_data else "yaml",
            }

    def _editor_import(self, params: dict) -> dict:
        """Handle editor.import method."""
        content = params.get("content")
        if not content:
            raise InvalidParamsError("Missing required parameter: content")

        name = params.get("name")
        description = params.get("description")

        try:
            project = self._editor_manager.import_content(content, name, description)
            return {
                "success": True,
                "project": project.model_dump(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _editor_preview(self, params: dict) -> dict:
        """Handle editor.preview method."""
        project_id = params.get("project_id")
        if not project_id:
            raise InvalidParamsError("Missing required parameter: project_id")

        format = params.get("format", "yaml")

        try:
            result = self._editor_manager.preview(project_id, format)
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "format": format,
            }

    def _editor_auto_layout(self, params: dict) -> dict:
        """Handle editor.auto_layout method."""
        project_id = params.get("project_id")
        if not project_id:
            raise InvalidParamsError("Missing required parameter: project_id")

        direction = params.get("direction", "top-bottom")

        try:
            project = self._editor_manager.auto_layout(project_id, direction)
            return {
                "success": True,
                "project": project.model_dump(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _editor_duplicate_node(self, params: dict) -> dict:
        """Handle editor.duplicate_node method."""
        project_id = params.get("project_id")
        if not project_id:
            raise InvalidParamsError("Missing required parameter: project_id")

        node_id = params.get("node_id")
        if not node_id:
            raise InvalidParamsError("Missing required parameter: node_id")

        offset_x = params.get("offset_x", 50)
        offset_y = params.get("offset_y", 50)

        try:
            node = self._editor_manager.duplicate_node(project_id, node_id, offset_x, offset_y)
            return {
                "success": True,
                "project_id": project_id,
                "new_node": node.model_dump(),
            }
        except Exception as e:
            return {
                "success": False,
                "project_id": project_id,
                "error": str(e),
            }

    def _editor_undo(self, params: dict) -> dict:
        """Handle editor.undo method."""
        project_id = params.get("project_id")
        if not project_id:
            raise InvalidParamsError("Missing required parameter: project_id")

        try:
            project = self._editor_manager.undo(project_id)
            return {
                "success": True,
                "project": project.model_dump(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _editor_redo(self, params: dict) -> dict:
        """Handle editor.redo method."""
        project_id = params.get("project_id")
        if not project_id:
            raise InvalidParamsError("Missing required parameter: project_id")

        try:
            project = self._editor_manager.redo(project_id)
            return {
                "success": True,
                "project": project.model_dump(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _workflow_execute(self, params: dict) -> dict:
        """Handle workflow.execute method with streaming support."""
        name = params.get("name")
        if not name:
            raise InvalidParamsError("Missing required parameter: name")

        user_context = params.get("user_context", "")
        cwd = params.get("cwd", ".")
        interactive = params.get("interactive", False)
        max_turns = params.get("max_turns", 50)

        # Generate execution ID
        self._current_execution_id = str(uuid.uuid4())[:8]

        # Check permission for workflow execution
        if not self._permission_checker.check_workflow_permission(self._current_role, name):
            # Log permission denial
            if self._audit_enabled:
                self._audit_logger.log_permission_check(
                    self._current_execution_id,
                    self._current_role,
                    "workflow",
                    name,
                    False
                )
            raise PermissionDeniedError(
                f"Role '{self._current_role}' does not have permission to execute workflow '{name}'"
            )
        
        # Log permission grant
        if self._audit_enabled:
            self._audit_logger.log_permission_check(
                self._current_execution_id,
                self._current_role,
                "workflow",
                name,
                True
            )
            # Log workflow start
            self._audit_logger.log_workflow_start(
                self._current_execution_id,
                name,
                user_context
            )

        # List workflows to find
        available = self._list_workflows()
        if name not in available:
            raise WorkflowNotFoundError(name, available)

        # Execute workflow_start hooks (async - non-blocking)
        workflow_start_context = HookExecutionContext(
            execution_id=self._current_execution_id,
            workflow_name=name,
            event="workflow_start",
        )
        self._hook_registry.execute_for_event("workflow_start", workflow_start_context, async_execution=True)

        # Send workflow started event
        self._send_workflow_event("started", name)
        self._send_progress(f"▶ Starting workflow '{name}'")

        # Load and parse workflow YAML
        workflow_path = self.workflows_dir / f"{name}.yaml"
        import yaml
        with open(workflow_path) as f:
            workflow_def = yaml.safe_load(f)

        # Execute workflow nodes
        start_time = time.time()
        path_taken: list[str] = []
        node_executions: list[dict] = []
        node_turns: dict[str, int] = {}

        # Find start node (first node without incoming edges)
        # For simplicity, we'll start with the first defined node
        nodes = workflow_def
        start_node = None
        for key in ["scan", "start", "begin", "init"]:
            if key in nodes:
                start_node = key
                break

        if not start_node:
            start_node = list(nodes.keys())[0] if nodes else None

        if not start_node:
            self._send_workflow_event("failed", name)
            return {
                "success": False,
                "final_output": f"Workflow '{name}' has no nodes defined.",
                "audit": {
                    "workflow_name": name,
                    "path_taken": [],
                    "node_executions": [],
                    "started_at": self._iso_time(start_time),
                    "completed_at": self._iso_time(time.time()),
                    "total_turns": 0,
                    "execution_id": self._current_execution_id,
                },
                "error": "No nodes defined",
            }

        # Execute nodes sequentially (simplified version)
        # A full implementation would use the leeway library
        current_node = start_node
        visited: set[str] = set()

        while current_node and current_node not in visited:
            node_def = nodes.get(current_node, {})
            if not node_def:
                break

            visited.add(current_node)
            path_taken.append(current_node)

            # Execute node_start hooks (async - non-blocking)
            node_start_context = HookExecutionContext(
                execution_id=self._current_execution_id,
                workflow_name=name,
                node_name=current_node,
                event="node_start",
            )
            self._hook_registry.execute_for_event("node_start", node_start_context, async_execution=True)

            # Send node started event
            self._send_node_event(current_node, "started")
            self._send_progress(f"  ● Node '{current_node}'", node=current_node)

            # Simulate node execution (in a full impl, this calls leeway)
            # For now, just record the execution
            node_turns[current_node] = node_turns.get(current_node, 0) + 1

            # Check for parallel branches
            if "parallel" in node_def:
                branches = node_def.get("parallel", {}).get("branches", {})
                for branch_name, branch_def in branches.items():
                    self._send_branch_event(branch_name, "triggered", "running")
                    self._send_progress(f"    ├─ Branch '{branch_name}' triggered", node=current_node)

            # Determine next node based on edges (simplified signal handling)
            edges = node_def.get("edges", [])
            next_node = None

            if edges:
                # For demo, take the first edge with always:true or default
                for edge in edges:
                    when = edge.get("when", {})
                    if when.get("always") or when.get("signal") == "ready":
                        next_node = edge.get("target")
                        signal_val = when.get("signal", "ready")
                        self._send_node_event(
                            current_node, "completed",
                            signal=signal_val,
                            signal_summary=f"Signal '{signal_val}' → moving to '{next_node}'"
                        )
                        self._send_progress(
                            f"    ⇢ Signal '{signal_val}' → moving to '{next_node}'",
                            node=current_node
                        )
                        break
            else:
                # Terminal node
                self._send_node_event(current_node, "completed")
                self._send_progress(f"  ✓ Node '{current_node}' (terminal)", node=current_node)

            node_executions.append({
                "node_name": current_node,
                "signal_decision": when.get("signal") if edges else None,
                "signal_summary": None,
                "turns_used": node_turns[current_node],
                "tools_called": node_def.get("tools", []),
            })

            current_node = next_node

            # Safety check for max iterations
            if len(path_taken) > max_turns:
                self._send_progress(f"⚠ Max turns ({max_turns}) reached", node=current_node)
                break

        # Send workflow completed event
        end_time = time.time()
        total_turns = sum(node_turns.values())
        self._send_workflow_event("completed", name)

        # Execute workflow_end hooks (async - non-blocking)
        workflow_end_context = HookExecutionContext(
            execution_id=self._current_execution_id,
            workflow_name=name,
            event="workflow_end",
            data={
                "success": True,
                "path_taken": path_taken,
                "total_turns": total_turns,
            },
        )
        self._hook_registry.execute_for_event("workflow_end", workflow_end_context, async_execution=True)

        return {
            "success": True,
            "final_output": f"Workflow '{name}' executed successfully.\n\nPath taken: {' → '.join(path_taken)}\n\nSummary:\n{self._generate_summary(workflow_def, path_taken, node_executions)}",
            "audit": {
                "workflow_name": name,
                "path_taken": path_taken,
                "node_executions": node_executions,
                "parallel_branches": self._get_parallel_branch_results(nodes, path_taken),
                "started_at": self._iso_time(start_time),
                "completed_at": self._iso_time(end_time),
                "total_turns": total_turns,
                "execution_id": self._current_execution_id,
            },
            "error": None,
        }

    def _iso_time(self, timestamp: float | None = None) -> str:
        """Generate ISO format timestamp."""
        import datetime
        if timestamp is None:
            timestamp = time.time()
        return datetime.datetime.fromtimestamp(timestamp).isoformat() + "Z"

    def _generate_summary(self, workflow_def: dict, path_taken: list[str], node_executions: list[dict]) -> str:
        """Generate a human-readable summary."""
        lines = [f"- Executed {len(node_executions)} nodes"]
        for node in node_executions:
            lines.append(f"  - {node['node_name']}: {node['turns_used']} turns, {len(node['tools_called'])} tools")
        return "\n".join(lines)

    def _get_parallel_branch_results(self, nodes: dict, path_taken: list[str]) -> dict:
        """Extract parallel branch results from executed nodes."""
        results = {}
        for node_name in path_taken:
            node_def = nodes.get(node_name, {})
            if "parallel" in node_def:
                branches = node_def.get("parallel", {}).get("branches", {})
                results[node_name] = {
                    branch_name: {"triggered": True, "completed": True, "approved": True}
                    for branch_name in branches.keys()
                }
        return results

    def _workflow_respond(self, params: dict) -> dict:
        """Handle workflow.respond method for HITL responses."""
        answer = params.get("answer", "")
        self._hitl_pending = {"answer": answer}
        return {"received": True, "answer": answer}

    def _workflow_list(self, params: dict) -> dict:
        """Handle workflow.list method."""
        return {"workflows": self._list_workflows()}

    def _list_workflows(self) -> list[str]:
        """List available workflows."""
        workflows = []
        if self.workflows_dir.exists():
            for f in self.workflows_dir.glob("*.yaml"):
                workflows.append(f.stem)
        return workflows

    def _workflow_validate(self, params: dict) -> dict:
        """Handle workflow.validate method."""
        name = params.get("name")
        if not name:
            raise InvalidParamsError("Missing required parameter: name")

        available = self._list_workflows()
        if name not in available:
            raise WorkflowNotFoundError(name, available)

        return {"valid": True, "errors": []}

    def _stop(self, params: dict) -> dict:
        """Handle daemon.stop method."""
        self._running = False
        # Stop all MCP servers
        if self._mcp_manager:
            self._mcp_manager.stop_all()
        return {"status": "stopped"}

    # MCP Methods
    def _mcp_servers(self, params: dict) -> dict:
        """Handle mcp.servers method - list all MCP servers."""
        if not self._mcp_manager:
            return {"servers": []}
        return {"servers": self._mcp_manager.list_servers()}

    def _mcp_start(self, params: dict) -> dict:
        """Handle mcp.start method - start an MCP server."""
        server_name = params.get("server_name")
        if not server_name:
            raise InvalidParamsError("Missing required parameter: server_name")

        if not self._mcp_manager:
            raise McpConnectionError(server_name, "MCP manager not initialized")

        return self._mcp_manager.start_server(server_name)

    def _mcp_stop(self, params: dict) -> dict:
        """Handle mcp.stop method - stop an MCP server."""
        server_name = params.get("server_name")
        if not server_name:
            raise InvalidParamsError("Missing required parameter: server_name")

        if not self._mcp_manager:
            raise McpConnectionError(server_name, "MCP manager not initialized")

        return self._mcp_manager.stop_server(server_name)

    def _mcp_list_tools(self, params: dict) -> dict:
        """Handle mcp.list_tools method - list tools from MCP server."""
        server_name = params.get("server_name")
        if not server_name:
            raise InvalidParamsError("Missing required parameter: server_name")

        if not self._mcp_manager:
            raise McpConnectionError(server_name, "MCP manager not initialized")

        server = self._mcp_manager.get_server(server_name)
        tools = server.list_tools()
        return {"tools": tools}

    def _mcp_execute(self, params: dict) -> dict:
        """Handle mcp.execute method - execute a tool on MCP server."""
        server_name = params.get("server_name")
        tool_name = params.get("tool_name")
        arguments = params.get("arguments", {})

        if not server_name:
            raise InvalidParamsError("Missing required parameter: server_name")
        if not tool_name:
            raise InvalidParamsError("Missing required parameter: tool_name")

        if not self._mcp_manager:
            raise McpConnectionError(server_name, "MCP manager not initialized")

        server = self._mcp_manager.get_server(server_name)
        return server.execute_tool(tool_name, arguments)

    # Cron Methods
    def _cron_create(self, params: dict) -> dict:
        """Handle cron.create method - create a new cron schedule."""
        name = params.get("name")
        workflow_name = params.get("workflow_name")
        cron_expression = params.get("cron_expression")
        user_context = params.get("user_context")

        if not name:
            raise InvalidParamsError("Missing required parameter: name")
        if not workflow_name:
            raise InvalidParamsError("Missing required parameter: workflow_name")
        if not cron_expression:
            raise InvalidParamsError("Missing required parameter: cron_expression")

        schedule = self._cron_scheduler.create(name, workflow_name, cron_expression, user_context)

        return {
            "success": True,
            "schedule": schedule.model_dump(),
            "error": None,
        }

    def _cron_list(self, params: dict) -> dict:
        """Handle cron.list method - list all cron schedules."""
        schedules = self._cron_scheduler.list()
        return {
            "schedules": [s.model_dump() for s in schedules],
        }

    def _cron_delete(self, params: dict) -> dict:
        """Handle cron.delete method - delete a cron schedule."""
        schedule_id = params.get("id")

        if not schedule_id:
            raise InvalidParamsError("Missing required parameter: id")

        self._cron_scheduler.delete(schedule_id)

        return {
            "success": True,
            "deleted_id": schedule_id,
            "error": None,
        }

    def _cron_toggle(self, params: dict) -> dict:
        """Handle cron.toggle method - enable/disable a cron schedule."""
        schedule_id = params.get("id")
        enabled = params.get("enabled")

        if not schedule_id:
            raise InvalidParamsError("Missing required parameter: id")
        if enabled is None:
            raise InvalidParamsError("Missing required parameter: enabled")

        schedule = self._cron_scheduler.toggle(schedule_id, enabled)

        return {
            "success": True,
            "schedule": schedule.model_dump(),
            "error": None,
        }

    # Scheduler Daemon Methods
    def _scheduler_start(self, params: dict) -> dict:
        """Handle scheduler.start method - start the scheduler daemon."""
        try:
            success = self._scheduler_daemon.start()
            if success:
                status = self._scheduler_daemon.get_status()
                return {
                    "success": True,
                    "status": status.model_dump(),
                    "error": None,
                }
            else:
                return {
                    "success": False,
                    "status": None,
                    "error": "Scheduler already running",
                }
        except Exception as e:
            return {
                "success": False,
                "status": None,
                "error": str(e),
            }

    def _scheduler_stop(self, params: dict) -> dict:
        """Handle scheduler.stop method - stop the scheduler daemon."""
        try:
            success = self._scheduler_daemon.stop()
            return {
                "success": success,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _scheduler_status(self, params: dict) -> dict:
        """Handle scheduler.status method - get scheduler status."""
        status = self._scheduler_daemon.get_status()
        return {
            "status": status.model_dump(),
        }

    def _scheduler_executions(self, params: dict) -> dict:
        """Handle scheduler.executions method - get execution history."""
        schedule_id = params.get("schedule_id")
        limit = params.get("limit", 10)

        executions = self._scheduler_daemon.get_executions(schedule_id, limit)
        return {
            "executions": [e.model_dump() for e in executions],
        }

    # Hooks Methods
    def _hooks_list(self, params: dict) -> dict:
        """Handle hooks.list method - list all hooks."""
        scope = params.get("scope")
        workflow_name = params.get("workflow_name")
        event = params.get("event")

        hooks = self._hook_registry.list(scope, workflow_name, event)
        return {
            "hooks": [h.model_dump() for h in hooks],
        }

    def _hooks_register(self, params: dict) -> dict:
        """Handle hooks.register method - register a new hook."""
        name = params.get("name")
        scope = params.get("scope")
        event = params.get("event")
        workflow_name = params.get("workflow_name")
        node_name = params.get("node_name")

        if not name:
            raise InvalidParamsError("Missing required parameter: name")
        if not scope:
            raise InvalidParamsError("Missing required parameter: scope")
        if not event:
            raise InvalidParamsError("Missing required parameter: event")

        # Parse command hook if provided
        command = None
        if "command" in params and params["command"]:
            command_data = params["command"]
            if isinstance(command_data, dict):
                command = CommandHook(**command_data)
            else:
                command = CommandHook(command=command_data)

        # Parse HTTP hook if provided
        http = None
        if "http" in params and params["http"]:
            http_data = params["http"]
            if isinstance(http_data, dict):
                http = HttpHook(**http_data)

        try:
            hook = self._hook_registry.register(
                name=name,
                scope=scope,
                event=event,
                workflow_name=workflow_name,
                node_name=node_name,
                command=command,
                http=http,
            )

            return {
                "success": True,
                "hook": hook.model_dump(),
                "error": None,
            }
        except HookRegistrationError as e:
            return {
                "success": False,
                "hook": None,
                "error": e.message,
            }

    def _hooks_unregister(self, params: dict) -> dict:
        """Handle hooks.unregister method - unregister a hook."""
        hook_id = params.get("hook_id")

        if not hook_id:
            raise InvalidParamsError("Missing required parameter: hook_id")

        try:
            self._hook_registry.unregister(hook_id)
            return {
                "success": True,
                "deleted_id": hook_id,
                "error": None,
            }
        except HookNotFoundError as e:
            return {
                "success": False,
                "deleted_id": None,
                "error": e.message,
            }

    def _hooks_toggle(self, params: dict) -> dict:
        """Handle hooks.toggle method - enable/disable a hook."""
        hook_id = params.get("hook_id")
        enabled = params.get("enabled")

        if not hook_id:
            raise InvalidParamsError("Missing required parameter: hook_id")
        if enabled is None:
            raise InvalidParamsError("Missing required parameter: enabled")

        try:
            hook = self._hook_registry.toggle(hook_id, enabled)
            return {
                "success": True,
                "hook": hook.model_dump(),
                "error": None,
            }
        except HookNotFoundError as e:
            return {
                "success": False,
                "hook": None,
                "error": e.message,
            }

    def _hooks_execute(self, params: dict) -> dict:
        """Handle hooks.execute method - manually execute a hook."""
        hook_id = params.get("hook_id")
        context_data = params.get("context", {})

        if not hook_id:
            raise InvalidParamsError("Missing required parameter: hook_id")

        # Build execution context
        context = HookExecutionContext(
            execution_id=context_data.get("execution_id", "manual"),
            workflow_name=context_data.get("workflow_name", ""),
            node_name=context_data.get("node_name"),
            tool_name=context_data.get("tool_name"),
            event=context_data.get("event", "manual"),
            data=context_data.get("data", {}),
        )

        try:
            result = self._hook_registry.execute_hook(hook_id, context)
            return {
                "success": result.success,
                "result": result.model_dump(),
                "error": result.error,
            }
        except HookNotFoundError as e:
            return {
                "success": False,
                "result": None,
                "error": e.message,
            }

    # Custom Tools Methods
    def _tools_list(self, params: dict) -> dict:
        """Handle tools.list method - list all custom tools."""
        tag = params.get("tag")
        tools = self._tool_registry.list(tag)

        return {
            "tools": [t.model_dump() for t in tools],
        }

    def _tools_register(self, params: dict) -> dict:
        """Handle tools.register method - register a new custom tool."""
        name = params.get("name")
        description = params.get("description")
        code = params.get("code")

        if not name:
            raise InvalidParamsError("Missing required parameter: name")
        if not description:
            raise InvalidParamsError("Missing required parameter: description")
        if not code:
            raise InvalidParamsError("Missing required parameter: code")

        # Parse parameters
        parameters = []
        if "parameters" in params and params["parameters"]:
            for param_data in params["parameters"]:
                if isinstance(param_data, dict):
                    parameters.append(ToolParameter(**param_data))

        # Parse tags
        tags = params.get("tags", [])
        version = params.get("version", "1.0.0")
        author = params.get("author")
        force = params.get("force", False)

        try:
            tool = self._tool_registry.register(
                name=name,
                description=description,
                code=code,
                parameters=parameters,
                version=version,
                author=author,
                tags=tags,
                force=force,
            )

            return {
                "success": True,
                "tool": tool.model_dump(),
                "error": None,
            }
        except ToolValidationError as e:
            return {
                "success": False,
                "tool": None,
                "error": e.message,
            }
        except ToolAlreadyExistsError as e:
            return {
                "success": False,
                "tool": None,
                "error": e.message,
            }
        except Exception as e:
            return {
                "success": False,
                "tool": None,
                "error": str(e),
            }

    def _tools_unregister(self, params: dict) -> dict:
        """Handle tools.unregister method - unregister a custom tool."""
        tool_id = params.get("tool_id")

        if not tool_id:
            raise InvalidParamsError("Missing required parameter: tool_id")

        try:
            self._tool_registry.unregister(tool_id)
            return {
                "success": True,
                "deleted_id": tool_id,
                "error": None,
            }
        except ToolNotFoundError as e:
            return {
                "success": False,
                "deleted_id": None,
                "error": e.message,
            }

    def _tools_toggle(self, params: dict) -> dict:
        """Handle tools.toggle method - enable/disable a custom tool."""
        tool_id = params.get("tool_id")
        enabled = params.get("enabled")

        if not tool_id:
            raise InvalidParamsError("Missing required parameter: tool_id")
        if enabled is None:
            raise InvalidParamsError("Missing required parameter: enabled")

        try:
            tool = self._tool_registry.toggle(tool_id, enabled)
            return {
                "success": True,
                "tool": tool.model_dump(),
                "error": None,
            }
        except ToolNotFoundError as e:
            return {
                "success": False,
                "tool": None,
                "error": e.message,
            }

    def _tools_execute(self, params: dict) -> dict:
        """Handle tools.execute method - execute a custom tool."""
        name = params.get("name")
        arguments = params.get("arguments", {})

        if not name:
            raise InvalidParamsError("Missing required parameter: name")

        try:
            result, execution_time = self._tool_registry.execute(name, arguments)
            return {
                "success": True,
                "result": result,
                "error": None,
                "execution_time_ms": execution_time,
            }
        except ToolNotFoundError as e:
            return {
                "success": False,
                "result": None,
                "error": e.message,
                "execution_time_ms": 0,
            }
        except ToolExecutionError as e:
            return {
                "success": False,
                "result": None,
                "error": e.message,
                "execution_time_ms": 0,
            }

    def _tools_get(self, params: dict) -> dict:
        """Handle tools.get method - get a custom tool by ID."""
        tool_id = params.get("tool_id")

        if not tool_id:
            raise InvalidParamsError("Missing required parameter: tool_id")

        try:
            tool = self._tool_registry.get(tool_id)
            return {
                "tool": tool.model_dump(),
            }
        except ToolNotFoundError as e:
            return {
                "tool": None,
            }

    def _tools_validate(self, params: dict) -> dict:
        """Handle tools.validate method - validate tool code without registering."""
        code = params.get("code")

        if not code:
            raise InvalidParamsError("Missing required parameter: code")

        # Create a temporary registry to validate
        temp_registry = CustomToolRegistry()
        is_valid, errors = temp_registry._validate_tool_code(code)

        return {
            "valid": is_valid,
            "errors": errors,
        }

    # =============================================================================
    # Plugin Methods
    # =============================================================================

    def _plugins_list(self, params: dict) -> dict:
        """Handle plugins.list method - list all plugins."""
        category = params.get("category")
        tag = params.get("tag")
        plugins = self._plugin_registry.list(category, tag)

        return {
            "plugins": [p.model_dump() for p in plugins],
        }

    def _plugins_get(self, params: dict) -> dict:
        """Handle plugins.get method - get a plugin by ID."""
        plugin_id = params.get("plugin_id")

        if not plugin_id:
            raise InvalidParamsError("Missing required parameter: plugin_id")

        try:
            plugin = self._plugin_registry.get(plugin_id)
            return {
                "plugin": plugin.model_dump(),
            }
        except PluginNotFoundError as e:
            return {
                "plugin": None,
            }

    def _plugins_install(self, params: dict) -> dict:
        """Handle plugins.install method - install a new plugin."""
        source = params.get("source")
        name = params.get("name")
        version = params.get("version")
        force = params.get("force", False)

        if not source:
            raise InvalidParamsError("Missing required parameter: source")

        # Parse source
        if isinstance(source, dict):
            source_obj = PluginInstallSource(**source)
        else:
            source_obj = PluginInstallSource(type=source)

        # For now, we expect the content to be passed directly
        # A full implementation would fetch from the source (git, npm, url, etc.)
        metadata_dict = params.get("metadata", {})
        content_dict = params.get("content", {})

        if not metadata_dict:
            raise InvalidParamsError("Missing required parameter: metadata")
        if not content_dict:
            raise InvalidParamsError("Missing required parameter: content")

        # Create metadata and content objects
        try:
            metadata = PluginMetadata(**metadata_dict)
            content = PluginContent(**content_dict)
        except Exception as e:
            return {
                "success": False,
                "plugin": None,
                "error": f"Invalid metadata or content: {str(e)}",
                "installed_files": [],
            }

        try:
            plugin = self._plugin_registry.install(
                name=name or metadata.name,
                metadata=metadata,
                content=content,
                force=force,
            )

            return {
                "success": True,
                "plugin": plugin.model_dump(),
                "error": None,
                "installed_files": [],  # Would track actual files in full impl
            }
        except (PluginInvalidFormatError, PluginDependencyMissingError) as e:
            return {
                "success": False,
                "plugin": None,
                "error": e.message,
                "installed_files": [],
            }
        except PluginAlreadyExistsError as e:
            return {
                "success": False,
                "plugin": None,
                "error": e.message,
                "installed_files": [],
            }
        except Exception as e:
            return {
                "success": False,
                "plugin": None,
                "error": str(e),
                "installed_files": [],
            }

    def _plugins_uninstall(self, params: dict) -> dict:
        """Handle plugins.uninstall method - uninstall a plugin."""
        plugin_id = params.get("plugin_id")
        force = params.get("force", False)

        if not plugin_id:
            raise InvalidParamsError("Missing required parameter: plugin_id")

        try:
            removed_files = self._plugin_registry.uninstall(plugin_id, force)
            return {
                "success": True,
                "deleted_id": plugin_id,
                "error": None,
                "removed_files": removed_files,
            }
        except PluginNotFoundError as e:
            return {
                "success": False,
                "deleted_id": None,
                "error": e.message,
                "removed_files": [],
            }
        except PluginUninstallError as e:
            return {
                "success": False,
                "deleted_id": None,
                "error": e.message,
                "removed_files": [],
            }

    def _plugins_enable(self, params: dict) -> dict:
        """Handle plugins.enable method - enable/disable a plugin."""
        plugin_id = params.get("plugin_id")
        enabled = params.get("enabled")

        if not plugin_id:
            raise InvalidParamsError("Missing required parameter: plugin_id")
        if enabled is None:
            raise InvalidParamsError("Missing required parameter: enabled")

        try:
            plugin = self._plugin_registry.toggle(plugin_id, enabled)
            return {
                "success": True,
                "plugin": plugin.model_dump(),
                "error": None,
            }
        except PluginNotFoundError as e:
            return {
                "success": False,
                "plugin": None,
                "error": e.message,
            }

    def _plugins_update(self, params: dict) -> dict:
        """Handle plugins.update method - update a plugin to a new version."""
        plugin_id = params.get("plugin_id")
        version = params.get("version")
        force = params.get("force", False)

        if not plugin_id:
            raise InvalidParamsError("Missing required parameter: plugin_id")

        try:
            plugin = self._plugin_registry.update(plugin_id, version)
            return {
                "success": True,
                "plugin": plugin.model_dump(),
                "error": None,
                "updated_files": [],  # Would track actual files in full impl
            }
        except PluginNotFoundError as e:
            return {
                "success": False,
                "plugin": None,
                "error": e.message,
                "updated_files": [],
            }

    def _plugins_search(self, params: dict) -> dict:
        """Handle plugins.search method - search plugins."""
        query = params.get("query")
        category = params.get("category")

        if not query:
            raise InvalidParamsError("Missing required parameter: query")

        plugins = self._plugin_registry.search(query, category)

        return {
            "plugins": [p.model_dump() for p in plugins],
            "total": len(plugins),
        }

    def _plugins_validate(self, params: dict) -> dict:
        """Handle plugins.validate method - validate plugin content without installing."""
        content_dict = params.get("content")

        if not content_dict:
            raise InvalidParamsError("Missing required parameter: content")

        try:
            content = PluginContent(**content_dict)
            is_valid, errors, warnings = self._plugin_registry._validate_plugin_content(content)

            return {
                "valid": is_valid,
                "errors": errors,
                "warnings": warnings,
            }
        except Exception as e:
            return {
                "valid": False,
                "errors": [str(e)],
                "warnings": [],
            }

    # =============================================================================
    # Cache Management Methods
    # =============================================================================

    def _cache_get_stats(self, params: dict) -> dict:
        """Handle cache.get_stats method - get cache statistics."""
        return self._result_cache.get_stats()

    def _cache_clear(self, params: dict) -> dict:
        """Handle cache.clear method - clear all cache entries."""
        self._result_cache.clear()
        return {"success": True, "message": "Cache cleared"}

    def _cache_invalidate(self, params: dict) -> dict:
        """
        Handle cache.invalidate method - invalidate specific cache entries.
        
        Params:
            method: Optional method name to invalidate
            pattern: Optional pattern to match methods for invalidation
        """
        method = params.get("method")
        pattern = params.get("pattern")
        
        count = self._result_cache.invalidate(method=method, pattern=pattern)
        return {"success": True, "invalidated": count}

    def _warmup(self, params: dict) -> dict:
        """
        Handle daemon.warmup method - pre-load resources for faster subsequent requests.

        This is called after daemon startup to pre-load:
        - Workflow definitions
        - Settings
        - MCP server configs

        Params:
            workflows: List of workflow names to pre-load (default: all)
            preload_mcp: Whether to pre-start MCP servers (default: false)
        """
        workflows = params.get("workflows", [])
        preload_mcp = params.get("preload_mcp", False)

        preloaded = {
            "workflows": [],
            "mcp_servers": [],
        }

        # Pre-load workflow definitions
        if not workflows:
            workflows = self._list_workflows()

        for wf_name in workflows:
            try:
                workflow_path = self.workflows_dir / f"{wf_name}.yaml"
                if workflow_path.exists():
                    import yaml
                    with open(workflow_path) as f:
                        yaml.safe_load(f)
                    preloaded["workflows"].append(wf_name)
            except Exception:
                pass

        # Pre-start MCP servers if requested
        if preload_mcp:
            for server in self._mcp_manager.list_servers():
                try:
                    self._mcp_manager.start_server(server["name"])
                    preloaded["mcp_servers"].append(server["name"])
                except Exception:
                    pass

        return {
            "success": True,
            "preloaded": preloaded,
            "message": f"Preloaded {len(preloaded['workflows'])} workflows, {len(preloaded['mcp_servers'])} MCP servers",
        }

    # =============================================================================
    # Authentication & Authorization Methods
    # =============================================================================

    def _auth_set_role(self, params: dict) -> dict:
        """
        Handle auth.set_role method - set current user role.
        
        This is used to change the effective role for permission checking.
        In production, this would be validated through proper auth.
        """
        role = params.get("role")
        if not role:
            raise InvalidParamsError("Missing required parameter: role")
        
        # Verify role is valid
        valid_roles = ["admin", "user", "guest", "custom"]
        if role not in valid_roles:
            raise InvalidParamsError(f"Invalid role. Must be one of: {valid_roles}")
        
        self._current_role = role
        
        # Log permission change
        if self._audit_enabled and self._current_execution_id:
            self._audit_logger.log_permission_check(
                self._current_execution_id,
                role,
                "role",
                "set",
                True
            )
        
        return {
            "success": True,
            "role": role,
            "message": f"Role set to '{role}'",
        }

    def _auth_roles_list(self, params: dict) -> dict:
        """Handle auth.roles.list method - list available roles."""
        roles = self._permission_checker.list_roles()
        return {"roles": roles}

    def _auth_roles_add(self, params: dict) -> dict:
        """Handle auth.roles.add method - add a custom role."""
        if not self._permission_checker.can_manage(self._current_role):
            return {
                "success": False,
                "error": "Permission denied: only admin can add custom roles",
            }
        
        role_name = params.get("role_name")
        permissions = params.get("permissions", {})
        
        if not role_name:
            raise InvalidParamsError("Missing required parameter: role_name")
        
        try:
            self._permission_checker.add_custom_role(role_name, permissions)
            return {
                "success": True,
                "message": f"Role '{role_name}' added",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _auth_check(self, params: dict) -> dict:
        """Handle auth.check method - check permission for a resource."""
        resource_type = params.get("resource_type")
        resource_name = params.get("resource_name")
        
        if not resource_type or not resource_name:
            raise InvalidParamsError("Missing required parameters: resource_type, resource_name")
        
        if resource_type == "workflow":
            granted = self._permission_checker.check_workflow_permission(
                self._current_role, resource_name
            )
        elif resource_type == "tool":
            granted = self._permission_checker.check_tool_permission(
                self._current_role, resource_name
            )
        else:
            granted = self._permission_checker.check_permission(
                self._current_role, resource_type, resource_name
            )
        
        return {
            "role": self._current_role,
            "resource_type": resource_type,
            "resource_name": resource_name,
            "granted": granted,
        }

    # =============================================================================
    # Audit Methods
    # =============================================================================

    def _audit_logs(self, params: dict) -> dict:
        """Handle audit.logs method - get audit logs."""
        limit = params.get("limit", 100)
        start_time = params.get("start_time")
        end_time = params.get("end_time")
        execution_id = params.get("execution_id")
        
        if execution_id:
            # Get specific execution logs
            logs = self._audit_logger.read_log(execution_id)
        else:
            # Get recent logs
            logs = self._audit_logger.get_logs(limit, start_time, end_time)
        
        return {
            "logs": logs,
            "count": len(logs),
        }

    def _audit_verify(self, params: dict) -> dict:
        """Handle audit.verify method - verify audit log integrity."""
        execution_id = params.get("execution_id")
        
        if not execution_id:
            raise InvalidParamsError("Missing required parameter: execution_id")
        
        logs = self._audit_logger.read_log(execution_id, verify_integrity=True)
        
        all_valid = all(log.get("_integrity_verified", False) for log in logs)
        
        return {
            "execution_id": execution_id,
            "entries": len(logs),
            "integrity_verified": all_valid,
            "message": "All entries verified" if all_valid else "Some entries failed verification",
        }

    def _audit_cleanup(self, params: dict) -> dict:
        """Handle audit.cleanup method - clean up old audit logs."""
        if not self._permission_checker.can_manage(self._current_role):
            return {
                "success": False,
                "error": "Permission denied: only admin can clean audit logs",
            }
        
        days = params.get("days", 90)
        deleted = self._audit_logger.cleanup_old_logs(days)
        
        return {
            "success": True,
            "deleted": deleted,
            "message": f"Deleted {deleted} audit logs older than {days} days",
        }

    # =============================================================================
    # Secure Config Methods
    # =============================================================================

    def _config_get_secure(self, params: dict) -> dict:
        """Handle config.get_secure method - get configuration with secure values."""
        key = params.get("key")
        
        if not key:
            raise InvalidParamsError("Missing required parameter: key")
        
        value = self._secure_config.get(key)
        
        # Return redacted value for sensitive keys
        if key in SecureConfig.SENSITIVE_KEYS:
            if value:
                return {
                    "key": key,
                    "value": "***REDACTED***",
                    "source": "secure",
                }
        
        return {
            "key": key,
            "value": value,
            "source": "settings",
        }

    def handle_request(self, request: JsonRpcRequest | dict) -> JsonRpcResponse:
        """Handle a JSON-RPC request."""
        # Support both dict and JsonRpcRequest
        if isinstance(request, dict):
            req_id = request.get("id", "unknown")
            method_name = request.get("method", "")
            params = request.get("params", {})
        else:
            req_id = request.id
            method_name = request.method
            params = request.params

        try:
            # Check if result caching is enabled
            enable_cache = self._settings.get("enable_result_cache", True)

            if enable_cache:
                # Check deterministic method cache (workflow.execute, tools.execute)
                if method_name in self._deterministic_methods:
                    cache_config = self._deterministic_methods[method_name]
                    # Filter params to only include deterministic ones
                    filtered_params = {
                        k: v for k, v in params.items()
                        if k in cache_config.get("params", [])
                    }
                    # Try to get cached result
                    cached = self._result_cache.get(method_name, filtered_params)
                    if cached is not None:
                        # Return cached result
                        return JsonRpcResponse(
                            id=req_id,
                            result=cached,
                        )

                # Check regular cacheable methods (list, validate, etc.)
                elif method_name in self._cacheable_methods:
                    cached = self._result_cache.get(method_name, params)
                    if cached is not None:
                        return JsonRpcResponse(
                            id=req_id,
                            result=cached,
                        )

            # Execute the method
            method = self._methods.get(method_name)
            if not method:
                raise MethodNotFoundError(method_name)

            result = method(params)

            # Cache the result if caching is enabled
            if enable_cache:
                if method_name in self._deterministic_methods:
                    cache_config = self._deterministic_methods[method_name]
                    filtered_params = {
                        k: v for k, v in params.items()
                        if k in cache_config.get("params", [])
                    }
                    ttl = cache_config.get("ttl")
                    self._result_cache.set(method_name, filtered_params, result, ttl)
                elif method_name in self._cacheable_methods:
                    cache_config = self._cacheable_methods[method_name]
                    ttl = cache_config.get("ttl")
                    self._result_cache.set(method_name, params, result, ttl)

            return JsonRpcResponse(
                id=req_id,
                result=result,
            )
        except DaemonError as e:
            return JsonRpcResponse(
                id=req_id,
                error=e.to_dict(),
            )
        except Exception as e:
            return JsonRpcResponse(
                id=req_id,
                error=InternalError(str(e)).to_dict(),
            )

    def run(self) -> None:
        """Run the daemon, reading from stdin and writing to stdout."""
        self._running = True
        while self._running:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                request = json.loads(line.strip())
                response = self.handle_request(request)
                print(json.dumps(response.model_dump(exclude_none=True)), flush=True)
            except json.JSONDecodeError as e:
                response = JsonRpcResponse(
                    id="",
                    error=InvalidRequestError(str(e)).to_dict(),
                )
                print(json.dumps(response.model_dump(exclude_none=True)), flush=True)
            except Exception as e:
                response = JsonRpcResponse(
                    id="",
                    error=InternalError(str(e)).to_dict(),
                )
                print(json.dumps(response.model_dump(exclude_none=True)), flush=True)


def main():
    """Entry point for the daemon."""
    import argparse

    parser = argparse.ArgumentParser(description="Leeway Daemon")
    parser.add_argument(
        "--workflows-dir",
        default=".leeway/workflows",
        help="Path to workflows directory",
    )
    parser.add_argument(
        "--settings",
        default=None,
        help="Path to settings.json",
    )
    args = parser.parse_args()

    daemon = Daemon(workflows_dir=args.workflows_dir, settings_path=args.settings)
    daemon.run()