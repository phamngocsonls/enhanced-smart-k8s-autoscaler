"""
Mimir-compatible Prometheus Client with Multi-Tenancy Support

Supports both regular Prometheus and Grafana Mimir with tenant isolation.
"""

import logging
import requests
from typing import Dict, List, Optional, Any
from prometheus_api_client import PrometheusConnect
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class MimirPrometheusClient:
    """
    Mimir-compatible Prometheus client with multi-tenancy support.
    
    Features:
    - Works with both Prometheus and Mimir
    - Multi-tenant support via X-Scope-OrgID header
    - Authentication support (Basic Auth, Bearer Token)
    - Custom headers support
    """
    
    def __init__(
        self,
        url: str,
        tenant_id: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        bearer_token: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        disable_ssl: bool = True,
        timeout: int = 30
    ):
        """
        Initialize Mimir/Prometheus client.
        
        Args:
            url: Prometheus/Mimir URL
            tenant_id: Mimir tenant ID (for multi-tenancy)
            username: Basic auth username
            password: Basic auth password
            bearer_token: Bearer token for authentication
            custom_headers: Additional headers
            disable_ssl: Disable SSL verification
            timeout: Request timeout in seconds
        """
        self.url = url.rstrip('/')
        self.tenant_id = tenant_id
        self.timeout = timeout
        self.disable_ssl = disable_ssl
        
        # Build headers
        self.headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        
        # Add Mimir tenant header
        if tenant_id:
            self.headers['X-Scope-OrgID'] = tenant_id
            logger.info(f"Mimir client initialized with tenant: {tenant_id}")
        
        # Add custom headers
        if custom_headers:
            self.headers.update(custom_headers)
        
        # Setup authentication
        self.auth = None
        if username and password:
            self.auth = (username, password)
            logger.info(f"Using Basic Auth with username: {username}")
        elif bearer_token:
            self.headers['Authorization'] = f'Bearer {bearer_token}'
            logger.info("Using Bearer token authentication")
        
        # Create fallback PrometheusConnect client for compatibility
        try:
            # For non-Mimir setups, use the original client
            if not tenant_id and not bearer_token and not custom_headers:
                self.prom_client = PrometheusConnect(
                    url=url,
                    disable_ssl=disable_ssl,
                    headers=self.headers if custom_headers else None
                )
                self.use_fallback = True
                logger.info("Using PrometheusConnect fallback client")
            else:
                self.prom_client = None
                self.use_fallback = False
                logger.info("Using native Mimir client")
        except Exception as e:
            logger.warning(f"Failed to create PrometheusConnect client: {e}")
            self.prom_client = None
            self.use_fallback = False
    
    def custom_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute a custom PromQL query.
        
        Args:
            query: PromQL query string
        
        Returns:
            List of query results
        """
        # Try fallback client first for compatibility
        if self.use_fallback and self.prom_client:
            try:
                return self.prom_client.custom_query(query)
            except Exception as e:
                logger.warning(f"Fallback client failed, using native: {e}")
                self.use_fallback = False
        
        # Use native implementation for Mimir/advanced features
        return self._native_query(query)
    
    def _native_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Native query implementation with Mimir support.
        
        Args:
            query: PromQL query string
        
        Returns:
            List of query results
        """
        try:
            # Build query URL
            query_url = urljoin(self.url, '/api/v1/query')
            
            # Prepare request
            params = {'query': query}
            
            # Make request
            response = requests.get(
                query_url,
                params=params,
                headers=self.headers,
                auth=self.auth,
                timeout=self.timeout,
                verify=not self.disable_ssl
            )
            
            # Check response
            response.raise_for_status()
            data = response.json()
            
            # Validate response format
            if data.get('status') != 'success':
                error_msg = data.get('error', 'Unknown error')
                logger.error(f"Prometheus query failed: {error_msg}")
                return []
            
            # Extract results
            result = data.get('data', {}).get('result', [])
            
            logger.debug(f"Query '{query[:50]}...' returned {len(result)} results")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Prometheus request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Prometheus query error: {e}")
            return []
    
    def custom_query_range(
        self,
        query: str,
        start_time: str,
        end_time: str,
        step: str = '1m'
    ) -> List[Dict[str, Any]]:
        """
        Execute a range query.
        
        Args:
            query: PromQL query string
            start_time: Start time (RFC3339 or Unix timestamp)
            end_time: End time (RFC3339 or Unix timestamp)
            step: Query resolution step
        
        Returns:
            List of query results
        """
        # Try fallback client first
        if self.use_fallback and self.prom_client:
            try:
                return self.prom_client.custom_query_range(
                    query=query,
                    start_time=start_time,
                    end_time=end_time,
                    step=step
                )
            except Exception as e:
                logger.warning(f"Fallback range query failed: {e}")
                self.use_fallback = False
        
        # Native implementation
        try:
            query_url = urljoin(self.url, '/api/v1/query_range')
            
            params = {
                'query': query,
                'start': start_time,
                'end': end_time,
                'step': step
            }
            
            response = requests.get(
                query_url,
                params=params,
                headers=self.headers,
                auth=self.auth,
                timeout=self.timeout,
                verify=not self.disable_ssl
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') != 'success':
                error_msg = data.get('error', 'Unknown error')
                logger.error(f"Range query failed: {error_msg}")
                return []
            
            result = data.get('data', {}).get('result', [])
            logger.debug(f"Range query returned {len(result)} series")
            return result
            
        except Exception as e:
            logger.error(f"Range query error: {e}")
            return []
    
    def get_label_values(self, label_name: str) -> List[str]:
        """
        Get all values for a label.
        
        Args:
            label_name: Label name
        
        Returns:
            List of label values
        """
        try:
            url = urljoin(self.url, f'/api/v1/label/{label_name}/values')
            
            response = requests.get(
                url,
                headers=self.headers,
                auth=self.auth,
                timeout=self.timeout,
                verify=not self.disable_ssl
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') != 'success':
                return []
            
            return data.get('data', [])
            
        except Exception as e:
            logger.error(f"Label values query error: {e}")
            return []
    
    def health_check(self) -> bool:
        """
        Check if Prometheus/Mimir is healthy.
        
        Returns:
            True if healthy
        """
        try:
            # Try a simple query
            result = self.custom_query('up')
            return len(result) > 0
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


def create_mimir_client(
    url: Optional[str] = None,
    tenant_id: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    bearer_token: Optional[str] = None,
    custom_headers: Optional[Dict[str, str]] = None
) -> MimirPrometheusClient:
    """
    Factory function to create Mimir client from environment variables.
    
    Environment variables:
        PROMETHEUS_URL: Prometheus/Mimir URL (required)
        MIMIR_TENANT_ID: Mimir tenant ID
        PROMETHEUS_USERNAME: Basic auth username
        PROMETHEUS_PASSWORD: Basic auth password
        PROMETHEUS_BEARER_TOKEN: Bearer token
        PROMETHEUS_CUSTOM_HEADERS: JSON string of custom headers
    
    Args:
        url: Override URL
        tenant_id: Override tenant ID
        username: Override username
        password: Override password
        bearer_token: Override bearer token
        custom_headers: Override custom headers
    
    Returns:
        MimirPrometheusClient instance
    """
    import json
    import os
    
    # Use provided values or fall back to environment
    final_url = url or os.getenv('PROMETHEUS_URL')
    final_tenant_id = tenant_id or os.getenv('MIMIR_TENANT_ID')
    final_username = username or os.getenv('PROMETHEUS_USERNAME')
    final_password = password or os.getenv('PROMETHEUS_PASSWORD')
    final_bearer_token = bearer_token or os.getenv('PROMETHEUS_BEARER_TOKEN')
    
    # Parse custom headers from JSON
    final_custom_headers = custom_headers
    if not final_custom_headers:
        headers_json = os.getenv('PROMETHEUS_CUSTOM_HEADERS')
        if headers_json:
            try:
                final_custom_headers = json.loads(headers_json)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid PROMETHEUS_CUSTOM_HEADERS JSON: {e}")
    
    if not final_url:
        raise ValueError("PROMETHEUS_URL is required")
    
    return MimirPrometheusClient(
        url=final_url,
        tenant_id=final_tenant_id,
        username=final_username,
        password=final_password,
        bearer_token=final_bearer_token,
        custom_headers=final_custom_headers
    )