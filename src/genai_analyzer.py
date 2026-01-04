"""
GenAI Analyzer for Smart Autoscaler
Provides natural language explanations for scaling decisions and anomalies.

Supported Providers:
- OpenAI (GPT-4, GPT-3.5)
- Google Gemini
- Anthropic Claude
- Mock (for testing)
"""

import logging
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import random
import requests
import time

# Try importing AI SDKs
try:
    import google.generativeai as genai
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    GOOGLE_GENAI_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

logger = logging.getLogger(__name__)

class GenAIAnalyzer:
    """
    Analyzer that uses GenAI (LLM) to provide context-aware explanations.
    
    Supported providers:
    - openai: OpenAI GPT-4/GPT-3.5
    - gemini: Google Gemini
    - claude: Anthropic Claude
    - mock: Mock responses (for testing)
    """
    
    def __init__(self, db, api_key: str = None, provider: str = None):
        self.db = db
        
        # Auto-detect provider from environment
        if not provider:
            if os.getenv("OPENAI_API_KEY"):
                provider = "openai"
            elif os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
                provider = "gemini"
            elif os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY"):
                provider = "claude"
            else:
                provider = "mock"
        
        self.provider = provider.lower()
        self.api_key = api_key or self._get_api_key()
        
        # Initialize provider
        if self.provider == "openai":
            self._init_openai()
        elif self.provider == "gemini":
            self._init_gemini()
        elif self.provider == "claude":
            self._init_claude()
        elif self.provider == "mock":
            logger.info("Using mock GenAI provider (no API key configured)")
        else:
            logger.warning(f"Unknown provider '{self.provider}', falling back to mock")
            self.provider = "mock"
    
    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment based on provider"""
        if self.provider == "openai":
            return os.getenv("OPENAI_API_KEY")
        elif self.provider == "gemini":
            return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        elif self.provider == "claude":
            return os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
        return None
    
    def _init_openai(self):
        """Initialize OpenAI"""
        if not OPENAI_AVAILABLE:
            logger.error("openai package not installed. Install: pip install openai")
            self.provider = "mock"
            return
        
        if not self.api_key:
            logger.warning("No OpenAI API key found, falling back to mock")
            self.provider = "mock"
            return
        
        openai.api_key = self.api_key
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # Fast and cheap
        logger.info(f"Using OpenAI provider (model={self.openai_model})")
    
    def _init_gemini(self):
        """Initialize Google Gemini"""
        if not GOOGLE_GENAI_AVAILABLE:
            logger.error("google-generativeai package not installed. Install: pip install google-generativeai")
            self.provider = "mock"
            return
        
        if not self.api_key:
            logger.warning("No Gemini API key found, falling back to mock")
            self.provider = "mock"
            return
        
        genai.configure(api_key=self.api_key)
        self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        logger.info("Using Gemini provider (model=gemini-1.5-flash)")
    
    def _init_claude(self):
        """Initialize Anthropic Claude"""
        if not ANTHROPIC_AVAILABLE:
            logger.error("anthropic package not installed. Install: pip install anthropic")
            self.provider = "mock"
            return
        
        if not self.api_key:
            logger.warning("No Claude API key found, falling back to mock")
            self.provider = "mock"
            return
        
        self.claude_client = anthropic.Anthropic(api_key=self.api_key)
        self.claude_model = os.getenv("CLAUDE_MODEL", "claude-3-haiku-20240307")  # Fast and cheap
        logger.info(f"Using Claude provider (model={self.claude_model})")
            
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
            elif self.provider == "openai":
                return self._call_openai(system_prompt, user_prompt)
            elif self.provider == "gemini":
                return self._call_gemini(system_prompt, user_prompt)
            elif self.provider == "claude":
                return self._call_claude(system_prompt, user_prompt)
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

    def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        """Call OpenAI API"""
        try:
            response = openai.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error calling OpenAI: {e}")
            return f"Error getting explanation from OpenAI: {str(e)}"
    
    def _call_gemini(self, system_prompt: str, user_prompt: str) -> str:
        """Call Gemini API"""
        try:
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            response = self.gemini_model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error calling Gemini: {e}")
            return f"Error getting explanation from Gemini: {str(e)}"
    
    def _call_claude(self, system_prompt: str, user_prompt: str) -> str:
        """Call Claude API"""
        try:
            response = self.claude_client.messages.create(
                model=self.claude_model,
                max_tokens=500,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Error calling Claude: {e}")
            return f"Error getting explanation from Claude: {str(e)}"
