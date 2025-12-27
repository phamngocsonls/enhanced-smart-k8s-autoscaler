"""
Structured Logging Configuration
JSON logging for better log aggregation and analysis
"""

import logging
import os
import sys
from typing import Optional

try:
    from pythonjsonlogger import jsonlogger
    JSON_LOGGING_AVAILABLE = True
except ImportError:
    JSON_LOGGING_AVAILABLE = False


def setup_structured_logging(
    log_level: str = "INFO",
    json_format: bool = None,
    extra_fields: Optional[dict] = None
) -> logging.Logger:
    """
    Setup structured logging with JSON format
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        json_format: Force JSON format (None = auto-detect from LOG_FORMAT env)
        extra_fields: Additional fields to include in all log entries
    
    Returns:
        Configured root logger
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Determine if JSON format should be used
    if json_format is None:
        log_format = os.getenv('LOG_FORMAT', 'json').lower()
        use_json = log_format == 'json' or log_format == 'structured'
    else:
        use_json = json_format
    
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    if use_json and JSON_LOGGING_AVAILABLE:
        # JSON formatter with extra fields
        format_string = '%(timestamp)s %(level)s %(name)s %(message)s'
        if extra_fields:
            # Add extra fields to format
            for key in extra_fields.keys():
                format_string += f' %({key})s'
        
        formatter = jsonlogger.JsonFormatter(
            format_string,
            timestamp=True
        )
        handler.setFormatter(formatter)
    else:
        # Standard formatter
        if use_json and not JSON_LOGGING_AVAILABLE:
            logging.warning(
                "JSON logging requested but python-json-logger not available. "
                "Using standard format. Install with: pip install python-json-logger"
            )
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
    
    root_logger.addHandler(handler)
    
    # Prevent propagation to avoid duplicate logs
    root_logger.propagate = False
    
    return root_logger


def get_logger(name: str, extra_context: Optional[dict] = None) -> logging.Logger:
    """
    Get a logger with optional extra context
    
    Args:
        name: Logger name (usually __name__)
        extra_context: Additional context to include in all log messages
    
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    if extra_context:
        # Create adapter to add extra context
        class ContextAdapter(logging.LoggerAdapter):
            def process(self, msg, kwargs):
                # Add extra context to all log records
                if 'extra' not in kwargs:
                    kwargs['extra'] = {}
                kwargs['extra'].update(self.extra)
                return msg, kwargs
        
        logger = ContextAdapter(logger, extra_context)
    
    return logger

