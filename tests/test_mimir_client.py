"""
Tests for Mimir client functionality
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests


class TestMimirPrometheusClient:
    """Test Mimir-compatible Prometheus client"""
    
    def test_mimir_client_import(self):
        """Test MimirPrometheusClient can be imported"""
        from src.mimir_client import MimirPrometheusClient
        assert MimirPrometheusClient is not None
    
    def test_mimir_client_initialization(self):
        """Test MimirPrometheusClient initializes correctly"""
        from src.mimir_client import MimirPrometheusClient
        
        client = MimirPrometheusClient(
            url="http://mimir:9090",
            tenant_id="test-tenant"
        )
        
        assert client.url == "http://mimir:9090"
        assert client.tenant_id == "test-tenant"
        assert client.headers['X-Scope-OrgID'] == "test-tenant"
    
    def test_mimir_client_with_auth(self):
        """Test MimirPrometheusClient with authentication"""
        from src.mimir_client import MimirPrometheusClient
        
        client = MimirPrometheusClient(
            url="http://mimir:9090",
            tenant_id="test-tenant",
            username="user",
            password="pass"
        )
        
        assert client.auth == ("user", "pass")
        assert client.headers['X-Scope-OrgID'] == "test-tenant"
    
    def test_mimir_client_with_bearer_token(self):
        """Test MimirPrometheusClient with bearer token"""
        from src.mimir_client import MimirPrometheusClient
        
        client = MimirPrometheusClient(
            url="http://mimir:9090",
            tenant_id="test-tenant",
            bearer_token="test-token"
        )
        
        assert client.headers['Authorization'] == "Bearer test-token"
        assert client.headers['X-Scope-OrgID'] == "test-tenant"
    
    def test_mimir_client_custom_headers(self):
        """Test MimirPrometheusClient with custom headers"""
        from src.mimir_client import MimirPrometheusClient
        
        custom_headers = {"X-Custom": "value"}
        client = MimirPrometheusClient(
            url="http://mimir:9090",
            custom_headers=custom_headers
        )
        
        assert client.headers['X-Custom'] == "value"
    
    @patch('src.mimir_client.requests.get')
    def test_native_query_success(self, mock_get):
        """Test native query implementation"""
        from src.mimir_client import MimirPrometheusClient
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            'status': 'success',
            'data': {
                'result': [
                    {'metric': {'__name__': 'up'}, 'value': [1234567890, '1']}
                ]
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        client = MimirPrometheusClient(url="http://mimir:9090")
        result = client.custom_query("up")
        
        assert len(result) == 1
        assert result[0]['metric']['__name__'] == 'up'
        mock_get.assert_called_once()
    
    @patch('src.mimir_client.requests.get')
    def test_native_query_failure(self, mock_get):
        """Test native query with failure"""
        from src.mimir_client import MimirPrometheusClient
        
        # Mock failed response
        mock_response = Mock()
        mock_response.json.return_value = {
            'status': 'error',
            'error': 'query failed'
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        client = MimirPrometheusClient(url="http://mimir:9090")
        result = client.custom_query("invalid_query")
        
        assert result == []
    
    @patch('src.mimir_client.requests.get')
    def test_native_query_exception(self, mock_get):
        """Test native query with exception"""
        from src.mimir_client import MimirPrometheusClient
        
        # Mock request exception
        mock_get.side_effect = requests.exceptions.RequestException("Connection failed")
        
        client = MimirPrometheusClient(url="http://mimir:9090")
        result = client.custom_query("up")
        
        assert result == []
    
    @patch('src.mimir_client.requests.get')
    def test_range_query(self, mock_get):
        """Test range query implementation"""
        from src.mimir_client import MimirPrometheusClient
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            'status': 'success',
            'data': {
                'result': [
                    {
                        'metric': {'__name__': 'cpu_usage'},
                        'values': [[1234567890, '0.5'], [1234567950, '0.6']]
                    }
                ]
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        client = MimirPrometheusClient(url="http://mimir:9090")
        result = client.custom_query_range(
            query="cpu_usage",
            start_time="2023-01-01T00:00:00Z",
            end_time="2023-01-01T01:00:00Z",
            step="1m"
        )
        
        assert len(result) == 1
        assert result[0]['metric']['__name__'] == 'cpu_usage'
        mock_get.assert_called_once()
    
    @patch('src.mimir_client.requests.get')
    def test_label_values(self, mock_get):
        """Test label values query"""
        from src.mimir_client import MimirPrometheusClient
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            'status': 'success',
            'data': ['value1', 'value2', 'value3']
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        client = MimirPrometheusClient(url="http://mimir:9090")
        result = client.get_label_values("job")
        
        assert result == ['value1', 'value2', 'value3']
        mock_get.assert_called_once()
    
    def test_health_check_success(self):
        """Test health check with successful query"""
        from src.mimir_client import MimirPrometheusClient
        
        client = MimirPrometheusClient(url="http://mimir:9090")
        
        # Mock custom_query to return results
        client.custom_query = Mock(return_value=[{'metric': {}, 'value': [123, '1']}])
        
        assert client.health_check() is True
    
    def test_health_check_failure(self):
        """Test health check with failed query"""
        from src.mimir_client import MimirPrometheusClient
        
        client = MimirPrometheusClient(url="http://mimir:9090")
        
        # Mock custom_query to return empty results
        client.custom_query = Mock(return_value=[])
        
        assert client.health_check() is False
    
    def test_health_check_exception(self):
        """Test health check with exception"""
        from src.mimir_client import MimirPrometheusClient
        
        client = MimirPrometheusClient(url="http://mimir:9090")
        
        # Mock custom_query to raise exception
        client.custom_query = Mock(side_effect=Exception("Query failed"))
        
        assert client.health_check() is False


class TestMimirClientFactory:
    """Test Mimir client factory function"""
    
    def test_create_mimir_client_import(self):
        """Test create_mimir_client can be imported"""
        from src.mimir_client import create_mimir_client
        assert create_mimir_client is not None
    
    @patch.dict('os.environ', {
        'PROMETHEUS_URL': 'http://test-mimir:9090',
        'MIMIR_TENANT_ID': 'test-tenant',
        'PROMETHEUS_USERNAME': 'user',
        'PROMETHEUS_PASSWORD': 'pass'
    })
    def test_create_mimir_client_from_env(self):
        """Test creating Mimir client from environment variables"""
        from src.mimir_client import create_mimir_client
        
        client = create_mimir_client()
        
        assert client.url == 'http://test-mimir:9090'
        assert client.tenant_id == 'test-tenant'
        assert client.auth == ('user', 'pass')
    
    def test_create_mimir_client_with_params(self):
        """Test creating Mimir client with explicit parameters"""
        from src.mimir_client import create_mimir_client
        
        client = create_mimir_client(
            url="http://custom-mimir:9090",
            tenant_id="custom-tenant",
            bearer_token="custom-token"
        )
        
        assert client.url == "http://custom-mimir:9090"
        assert client.tenant_id == "custom-tenant"
        assert client.headers['Authorization'] == "Bearer custom-token"
    
    def test_create_mimir_client_missing_url(self):
        """Test creating Mimir client without URL raises error"""
        from src.mimir_client import create_mimir_client
        
        with pytest.raises(ValueError, match="PROMETHEUS_URL is required"):
            create_mimir_client()
    
    @patch.dict('os.environ', {
        'PROMETHEUS_URL': 'http://test-mimir:9090',
        'PROMETHEUS_CUSTOM_HEADERS': '{"X-Custom": "value"}'
    })
    def test_create_mimir_client_custom_headers_json(self):
        """Test creating Mimir client with custom headers from JSON"""
        from src.mimir_client import create_mimir_client
        
        client = create_mimir_client()
        
        assert client.headers['X-Custom'] == 'value'
    
    @patch.dict('os.environ', {
        'PROMETHEUS_URL': 'http://test-mimir:9090',
        'PROMETHEUS_CUSTOM_HEADERS': 'invalid-json'
    })
    def test_create_mimir_client_invalid_headers_json(self):
        """Test creating Mimir client with invalid custom headers JSON"""
        from src.mimir_client import create_mimir_client
        
        # Should not raise exception, just log warning
        client = create_mimir_client()
        
        assert client.url == 'http://test-mimir:9090'


class TestMimirClientFallback:
    """Test Mimir client fallback to PrometheusConnect"""
    
    @patch('src.mimir_client.PrometheusConnect')
    def test_fallback_client_creation(self, mock_prometheus_connect):
        """Test fallback to PrometheusConnect for simple cases"""
        from src.mimir_client import MimirPrometheusClient
        
        # Mock PrometheusConnect
        mock_prom_client = Mock()
        mock_prometheus_connect.return_value = mock_prom_client
        
        client = MimirPrometheusClient(url="http://prometheus:9090")
        
        # Should create fallback client for simple case (no tenant, no auth)
        assert client.use_fallback is True
        assert client.prom_client == mock_prom_client
    
    @patch('src.mimir_client.PrometheusConnect')
    def test_no_fallback_with_tenant(self, mock_prometheus_connect):
        """Test no fallback when tenant is specified"""
        from src.mimir_client import MimirPrometheusClient
        
        client = MimirPrometheusClient(
            url="http://mimir:9090",
            tenant_id="test-tenant"
        )
        
        # Should not use fallback when tenant is specified
        assert client.use_fallback is False
    
    def test_fallback_query_success(self):
        """Test fallback query execution"""
        from src.mimir_client import MimirPrometheusClient
        
        client = MimirPrometheusClient(url="http://prometheus:9090")
        
        # Mock fallback client
        mock_result = [{'metric': {}, 'value': [123, '1']}]
        client.prom_client = Mock()
        client.prom_client.custom_query.return_value = mock_result
        client.use_fallback = True
        
        result = client.custom_query("up")
        
        assert result == mock_result
        client.prom_client.custom_query.assert_called_once_with("up")
    
    @patch('src.mimir_client.requests.get')
    def test_fallback_to_native_on_error(self, mock_get):
        """Test fallback to native implementation when PrometheusConnect fails"""
        from src.mimir_client import MimirPrometheusClient
        
        client = MimirPrometheusClient(url="http://prometheus:9090")
        
        # Mock fallback client to raise exception
        client.prom_client = Mock()
        client.prom_client.custom_query.side_effect = Exception("Fallback failed")
        client.use_fallback = True
        
        # Mock native query success
        mock_response = Mock()
        mock_response.json.return_value = {
            'status': 'success',
            'data': {'result': [{'metric': {}, 'value': [123, '1']}]}
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = client.custom_query("up")
        
        # Should fall back to native implementation
        assert len(result) == 1
        assert client.use_fallback is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])