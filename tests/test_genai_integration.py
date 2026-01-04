import unittest
from unittest.mock import MagicMock, patch
import json
from datetime import datetime

# Import dashboard (will import GenAIAnalyzer)
from src.dashboard import WebDashboard

class TestGenAIIntegration(unittest.TestCase):
    def setUp(self):
        # Mock DB
        self.mock_db = MagicMock()
        self.mock_db.get_recent_metrics.return_value = []
        # Mock Operator
        self.mock_operator = MagicMock()
        self.mock_operator.watched_deployments = {}
        
        # Initialize Dashboard
        self.dashboard = WebDashboard(self.mock_db, self.mock_operator)
        self.app = self.dashboard.app.test_client()

    def test_explain_endpoint(self):
        # Test valid request
        payload = {
            "deployment": "test-app",
            "query": "Why did it scale?"
        }
        
        response = self.app.post('/api/ai/explain', 
                               json=payload,
                               content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertIn('explanation', data)
        print(f"\nResponse: {data['explanation']}")
        self.assertEqual(data['deployment'], "test-app")
    
    def test_explain_endpoint_missing_data(self):
        response = self.app.post('/api/ai/explain', 
                               json={},
                               content_type='application/json')
        self.assertEqual(response.status_code, 400)

if __name__ == '__main__':
    unittest.main()
