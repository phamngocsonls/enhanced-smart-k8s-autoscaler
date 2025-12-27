"""
Resilience Patterns
Retry logic, circuit breakers, and error handling
"""

import time
import logging
from functools import wraps
from typing import Callable, TypeVar, Optional, Any
from threading import Lock

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitBreaker:
    """Circuit breaker pattern for external services"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60, name: str = "circuit"):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.name = name
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = 'closed'  # closed, open, half_open
        self.lock = Lock()
    
    def call(self, func: Callable[[], T], *args, **kwargs) -> Optional[T]:
        """Call function with circuit breaker protection"""
        with self.lock:
            if self.state == 'open':
                if self._should_attempt_reset():
                    logger.info(f"Circuit breaker {self.name}: Attempting reset (half-open)")
                    self.state = 'half_open'
                else:
                    logger.warning(f"Circuit breaker {self.name}: OPEN, skipping call")
                    return None
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            logger.error(f"Circuit breaker {self.name}: Call failed: {e}")
            raise
    
    def _on_success(self):
        """Reset on successful call"""
        with self.lock:
            self.failure_count = 0
            if self.state == 'half_open':
                logger.info(f"Circuit breaker {self.name}: Reset to CLOSED after successful call")
            self.state = 'closed'
    
    def _on_failure(self):
        """Track failure"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = 'open'
                logger.error(
                    f"Circuit breaker {self.name}: OPENED after {self.failure_count} failures. "
                    f"Will retry after {self.timeout}s"
                )
    
    def _should_attempt_reset(self) -> bool:
        """Check if should attempt reset"""
        if not self.last_failure_time:
            return True
        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.timeout
    
    def reset(self):
        """Manually reset circuit breaker"""
        with self.lock:
            self.failure_count = 0
            self.last_failure_time = None
            self.state = 'closed'
            logger.info(f"Circuit breaker {self.name}: Manually reset")


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,),
    log_retries: bool = True
):
    """
    Retry decorator with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        exceptions: Tuple of exceptions to catch and retry
        log_retries: Whether to log retry attempts
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        if log_retries:
                            logger.warning(
                                f"{func.__name__}: Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                                f"Retrying in {delay:.1f}s"
                            )
                        time.sleep(delay)
                        delay = min(delay * exponential_base, max_delay)
                    else:
                        logger.error(f"{func.__name__}: All {max_retries + 1} attempts failed. Last error: {e}")
            
            if last_exception:
                raise last_exception
            return None
        return wrapper
    return decorator


class RateLimiter:
    """Rate limiter for API calls"""
    
    def __init__(self, max_calls: int, time_window: float):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls: list[float] = []
        self.lock = Lock()
    
    def acquire(self):
        """Acquire rate limit permission, blocking if necessary"""
        with self.lock:
            now = time.time()
            # Remove old calls outside time window
            self.calls = [c for c in self.calls if now - c < self.time_window]
            
            if len(self.calls) >= self.max_calls:
                # Calculate sleep time until oldest call expires
                oldest_call = min(self.calls)
                sleep_time = self.time_window - (now - oldest_call) + 0.1  # Small buffer
                if sleep_time > 0:
                    logger.debug(f"Rate limit reached, sleeping {sleep_time:.2f}s")
                    
                    # Record rate limit delay if prometheus_exporter available
                    try:
                        import sys
                        if 'prometheus_exporter' in sys.modules:
                            from src.prometheus_exporter import PrometheusExporter
                            # Try to get instance and record delay
                            # This is a best-effort attempt
                            pass
                    except Exception:
                        pass
                    
                    time.sleep(sleep_time)
                    # Re-check after sleep
                    now = time.time()
                    self.calls = [c for c in self.calls if now - c < self.time_window]
            
            self.calls.append(time.time())

