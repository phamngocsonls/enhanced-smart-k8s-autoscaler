"""
Configuration Validator
Validates all environment variables and configuration values
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ConfigValidator:
    """Validate configuration values"""
    
    @staticmethod
    def validate_prometheus_url(url: str) -> str:
        """Validate Prometheus URL"""
        if not url:
            raise ValueError("PROMETHEUS_URL is required")
        if not url.startswith(('http://', 'https://')):
            raise ValueError(f"Invalid PROMETHEUS_URL format: {url}. Must start with http:// or https://")
        if len(url) > 2048:
            raise ValueError(f"PROMETHEUS_URL too long (max 2048 chars)")
        return url.strip()
    
    @staticmethod
    def validate_check_interval(interval: str) -> int:
        """Validate check interval"""
        try:
            value = int(interval)
            if value < 10:
                raise ValueError(f"CHECK_INTERVAL must be at least 10 seconds, got {value}")
            if value > 3600:
                raise ValueError(f"CHECK_INTERVAL must be at most 3600 seconds (1 hour), got {value}")
            return value
        except ValueError as e:
            if "invalid literal" in str(e):
                raise ValueError(f"Invalid CHECK_INTERVAL: {interval}. Must be an integer") from e
            raise
    
    @staticmethod
    def validate_target_utilization(value: str) -> float:
        """Validate target node utilization"""
        try:
            val = float(value)
            if val < 10.0:
                raise ValueError(f"TARGET_NODE_UTILIZATION must be at least 10%, got {val}")
            if val > 95.0:
                raise ValueError(f"TARGET_NODE_UTILIZATION must be at most 95%, got {val}")
            return val
        except ValueError as e:
            if "could not convert" in str(e):
                raise ValueError(f"Invalid TARGET_NODE_UTILIZATION: {value}. Must be a number") from e
            raise
    
    @staticmethod
    def validate_cost_per_vcpu(value: str) -> float:
        """Validate cost per vCPU"""
        try:
            val = float(value)
            if val < 0:
                raise ValueError(f"COST_PER_VCPU_HOUR must be non-negative, got {val}")
            if val > 100:
                raise ValueError(f"COST_PER_VCPU_HOUR seems too high: {val}. Check if value is correct")
            return val
        except ValueError as e:
            if "could not convert" in str(e):
                raise ValueError(f"Invalid COST_PER_VCPU_HOUR: {value}. Must be a number") from e
            raise
    
    @staticmethod
    def validate_db_path(path: str) -> str:
        """Validate database path"""
        if not path:
            raise ValueError("DB_PATH is required")
        if len(path) > 512:
            raise ValueError(f"DB_PATH too long (max 512 chars)")
        # Ensure path is absolute
        if not os.path.isabs(path):
            raise ValueError(f"DB_PATH must be absolute path, got: {path}")
        return path
    
    @staticmethod
    def validate_startup_filter(value: str) -> int:
        """Validate startup filter minutes"""
        try:
            val = int(value)
            if val < 0:
                raise ValueError(f"STARTUP_FILTER must be non-negative, got {val}")
            if val > 60:
                raise ValueError(f"STARTUP_FILTER should be at most 60 minutes, got {val}")
            return val
        except ValueError as e:
            if "invalid literal" in str(e):
                raise ValueError(f"Invalid STARTUP_FILTER: {value}. Must be an integer") from e
            raise
    
    @staticmethod
    def validate_port(port: str, name: str = "PORT") -> int:
        """Validate port number"""
        try:
            val = int(port)
            if val < 1 or val > 65535:
                raise ValueError(f"{name} must be between 1 and 65535, got {val}")
            return val
        except ValueError as e:
            if "invalid literal" in str(e):
                raise ValueError(f"Invalid {name}: {port}. Must be an integer") from e
            raise

