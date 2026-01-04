"""
GenAI Analyzer for Smart Autoscaler
Provides natural language explanations for scaling decisions and anomalies.
"""

import logging
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import random
import requests
import time
try:
    import google.generativeai as genai
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    GOOGLE_GENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

class GenAIAnalyzer:
    """
    Analyzer that uses GenAI (LLM) to provide context-aware explanations.
    """
    
    def __init__(self, db, api_key: str = None, provider: str = "mock"):
        self.db = db
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.provider = provider
        
        if not self.api_key and provider != "mock":
            # Auto-detect Ollama
            if provider == "ollama" or os.getenv("OLLAMA_HOST"):
                self.provider = "ollama"
                self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
                self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3")
                logger.info(f"Using Ollama provider ({self.ollama_host}, model={self.ollama_model})")
            else:
                logger.warning("No API key and no Ollama detected, falling back to mock provider")
                self.provider = "mock"
        
        if self.provider == "gemini" and self.api_key:
            if GOOGLE_GENAI_AVAILABLE:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
            else:
                logger.error("google-generativeai package not installed, falling back to mock")
                self.provider = "mock"
            
    def analyze_event(self, deployment: str, query: str, context_hours: int = 1) -> str:
        """
        Analyze a specific event or answer a query about a deployment.
        """
        try:
            # Gather context
            context = self._gather_context(deployment, hours=context_hours)
            
            # Construct prompt
            system_prompt = self._construct_system_prompt()
            user_prompt = self._construct_user_prompt(deployment, query, context)
            
            # Get response
            if self.provider == "mock":
                return self._mock_response(deployment, query, context)
            elif self.provider == "gemini":
                return self._call_gemini(system_prompt, user_prompt)
            elif self.provider == "ollama":
                return self._call_ollama(system_prompt, user_prompt)
            else:
                return self._mock_response(deployment, query, context)
                
        except Exception as e:
            logger.error(f"Error analyzing event: {e}", exc_info=True)
            return f"I apologize, but I encountered an error while analyzing the data: {str(e)}"

    def _gather_context(self, deployment: str, hours: int = 1) -> Dict:
        """Gather relevant context from database"""
        context = {
            "metrics": [],
            "anomalies": [],
            "predictions": [],
            "patterns": {},
            "scaling_events": []
        }
        
        try:
            # Get recent metrics
            recent = self.db.get_recent_metrics(deployment, hours=hours)
            if recent:
                # Downsample if too many
                step = max(1, len(recent) // 20)
                context["metrics"] = [
                    {
                        "time": m.timestamp.strftime("%H:%M"),
                        "cpu": f"{m.node_utilization:.1f}%",
                        "pods": m.pod_count,
                        "target": m.hpa_target
                    }
                    for m in recent[::step]
                ]
            
            # Get anomalies
            cursor = self.db.conn.execute("""
                SELECT timestamp, anomaly_type, description, severity
                FROM anomalies
                WHERE deployment = ? AND timestamp >= datetime('now', '-' || ? || ' hours')
            """, (deployment, hours))
            
            for row in cursor.fetchall():
                context["anomalies"].append({
                    "time": row[0],
                    "type": row[1],
                    "desc": row[2],
                    "severity": row[3]
                })

            # Get recent prediction
            cursor = self.db.conn.execute("""
                SELECT timestamp, predicted_cpu, confidence, recommended_action
                FROM predictions
                WHERE deployment = ? AND timestamp >= datetime('now', '-' || ? || ' hours')
                ORDER BY timestamp DESC LIMIT 5
            """, (deployment, hours))
             
            for row in cursor.fetchall():
                 context["predictions"].append({
                     "time": row[0],
                     "pred_cpu": row[1],
                     "conf": row[2],
                     "action": row[3]
                 })

        except Exception as e:
            logger.error(f"Error gathering context: {e}")
            
        return context

    def _construct_system_prompt(self) -> str:
        return """You are an intelligent Kubernetes Autoscaling Assistant. 
Your goal is to explain scaling behavior, anomalies, and performance issues to the user in simple, professional technical language.
Use the provided JSON context including metrics, anomalies, and logs to answer the user's question.
Be concise. Do not hallucinate data not present in the context."""

    def _construct_user_prompt(self, deployment: str, query: str, context: Dict) -> str:
        return f"""
Deployment: {deployment}
User Query: {query}
Context Data:
{json.dumps(context, indent=2)}

Please provide a helpful explanation based on this data.
"""

    def _mock_response(self, deployment: str, query: str, context: Dict) -> str:
        """Generate a convincing mock response based on available data"""
        
        # Check for obvious issues in context
        anomalies = context.get("anomalies", [])
        metrics = context.get("metrics", [])
        
        if "why" in query.lower() and "scale" in query.lower():
            if anomalies:
                latest = anomalies[0]
                return f"I noticed a {latest['severity']} anomaly ({latest['type']}) around {latest['time']}. This likely triggered the scaling logic to stabilize performance. {latest['desc']}."
            
            if metrics:
                # Check for trend
                latest_cpu = float(metrics[0]['cpu'].strip('%'))
                oldest_cpu = float(metrics[-1]['cpu'].strip('%'))
                if latest_cpu > oldest_cpu + 10:
                    return f"CPU utilization increased significantly from {oldest_cpu:.1f}% to {latest_cpu:.1f}% over the last hour. The autoscaler reacted by increasing pod count to maintain performance targets."
                elif latest_cpu < oldest_cpu - 10:
                     return f"CPU utilization dropped to {latest_cpu:.1f}%, indicating over-provisioning. The autoscaler reduced the replica count to optimize costs."
            
            return "The autoscaler is operating normally. I don't see any significant anomalies or spikes that would cause unusual behavior. Scaling actions are following the standard CPU utilization targets."

        return "I've analyzed the recent metrics. The system seems stable. CPU usage is within expected bounds, and no critical anomalies were detected in the last hour. Is there a specific time window you are interested in?"

    def _call_gemini(self, system_prompt: str, user_prompt: str) -> str:
        """Call Gemini API"""
        try:
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            response = self.model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error calling Gemini: {e}")
            return f"Error getting explanation from Gemini: {str(e)}"

    def _call_ollama(self, system_prompt: str, user_prompt: str) -> str:
        """Call local Ollama API"""
        try:
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            payload = {
                "model": self.ollama_model,
                "prompt": full_prompt,
                "stream": False
            }
            
            response = requests.post(f"{self.ollama_host}/api/generate", json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("response", "No response from Ollama")
            else:
                logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                return f"Error calling Ollama: {response.status_code}"
                
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            return f"Error getting explanation from local AI (Ollama). Is it running? ({str(e)})"
