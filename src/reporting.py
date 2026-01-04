"""
Advanced Reporting Module
Generate executive reports, trend analysis, and ROI calculations
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
from io import StringIO

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate various reports for cost, performance, and optimization"""
    
    def __init__(self, db, operator, cost_allocator):
        self.db = db
        self.operator = operator
        self.cost_allocator = cost_allocator
    
    def generate_executive_summary(self, days: int = 30) -> Dict:
        """Generate executive summary report"""
        try:
            # Get cost data
            current_costs = self.cost_allocator.get_team_costs(hours=24)
            cost_trends = self.cost_allocator.get_cost_trends(days=days)
            anomalies = self.cost_allocator.detect_cost_anomalies()
            idle_resources = self.cost_allocator.get_idle_resources()
            
            # Calculate totals
            total_daily_cost = sum(team['total_cost'] for team in current_costs.values())
            total_monthly_cost = total_daily_cost * 30
            
            # Calculate potential savings
            total_waste = sum(r['wasted_cost'] for r in idle_resources)
            monthly_waste = total_waste * 30
            
            # Get deployment count
            total_deployments = len(self.operator.watched_deployments)
            
            # Calculate efficiency score
            efficiency_score = self._calculate_efficiency_score()
            
            # Get scaling events
            scaling_events = self._get_scaling_events(days)
            
            return {
                'generated_at': datetime.now().isoformat(),
                'period_days': days,
                'summary': {
                    'total_deployments': total_deployments,
                    'daily_cost': round(total_daily_cost, 2),
                    'monthly_cost': round(total_monthly_cost, 2),
                    'efficiency_score': efficiency_score,
                    'potential_monthly_savings': round(monthly_waste, 2),
                    'savings_percentage': round((monthly_waste / total_monthly_cost * 100) if total_monthly_cost > 0 else 0, 1)
                },
                'cost_breakdown': {
                    'by_team': current_costs,
                    'trends': cost_trends['trends'][-30:],  # Last 30 days
                },
                'alerts': {
                    'cost_anomalies': anomalies,
                    'idle_resources': idle_resources[:10],  # Top 10
                    'anomaly_count': len(anomalies),
                    'idle_resource_count': len(idle_resources)
                },
                'scaling_activity': {
                    'total_events': scaling_events['total'],
                    'scale_ups': scaling_events['scale_ups'],
                    'scale_downs': scaling_events['scale_downs'],
                    'avg_per_day': round(scaling_events['total'] / days, 1)
                },
                'recommendations': self._generate_recommendations(idle_resources, anomalies)
            }
            
        except Exception as e:
            logger.error(f"Failed to generate executive summary: {e}")
            return {'error': str(e)}
    
    def generate_team_report(self, team: str, days: int = 30) -> Dict:
        """Generate detailed report for a specific team"""
        try:
            # Get team costs
            all_team_costs = self.cost_allocator.get_team_costs(hours=24)
            team_data = all_team_costs.get(team, {})
            
            if not team_data:
                return {'error': f'Team {team} not found'}
            
            # Get deployment details
            deployments = []
            for dep in team_data.get('deployments', []):
                namespace = dep['namespace']
                deployment = dep['deployment']
                
                # Get metrics
                metrics = self._get_deployment_metrics(namespace, deployment, days)
                
                deployments.append({
                    'namespace': namespace,
                    'deployment': deployment,
                    'daily_cost': dep['cost'],
                    'monthly_cost': round(dep['cost'] * 30, 2),
                    'metrics': metrics
                })
            
            return {
                'team': team,
                'generated_at': datetime.now().isoformat(),
                'period_days': days,
                'summary': {
                    'deployment_count': team_data.get('deployment_count', 0),
                    'daily_cost': team_data.get('total_cost', 0),
                    'monthly_cost': round(team_data.get('total_cost', 0) * 30, 2),
                    'cpu_cost': team_data.get('cpu_cost', 0),
                    'memory_cost': team_data.get('memory_cost', 0)
                },
                'deployments': deployments
            }
            
        except Exception as e:
            logger.error(f"Failed to generate team report: {e}")
            return {'error': str(e)}
    
    def generate_cost_forecast(self, days_ahead: int = 90) -> Dict:
        """Forecast future costs based on trends"""
        try:
            # Get historical trends
            trends = self.cost_allocator.get_cost_trends(days=30)
            
            if not trends.get('trends') or len(trends['trends']) < 7:
                return {'error': 'Insufficient historical data for forecasting'}
            
            # Simple linear regression for forecast
            costs = [t['total_cost'] for t in trends['trends']]
            
            # Calculate trend
            n = len(costs)
            x = list(range(n))
            y = costs
            
            x_mean = sum(x) / n
            y_mean = sum(y) / n
            
            numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
            denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
            
            if denominator == 0:
                slope = 0
            else:
                slope = numerator / denominator
            
            intercept = y_mean - slope * x_mean
            
            # Generate forecast
            forecast = []
            for i in range(days_ahead):
                future_day = n + i
                predicted_cost = slope * future_day + intercept
                forecast_date = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
                
                forecast.append({
                    'date': forecast_date,
                    'predicted_cost': round(max(0, predicted_cost), 2),
                    'confidence': 'high' if i < 30 else 'medium' if i < 60 else 'low'
                })
            
            # Calculate totals
            total_30_day = sum(f['predicted_cost'] for f in forecast[:30])
            total_60_day = sum(f['predicted_cost'] for f in forecast[:60])
            total_90_day = sum(f['predicted_cost'] for f in forecast[:90])
            
            return {
                'generated_at': datetime.now().isoformat(),
                'forecast_days': days_ahead,
                'trend': 'increasing' if slope > 0 else 'decreasing' if slope < 0 else 'stable',
                'daily_change': round(slope, 2),
                'forecasts': forecast,
                'totals': {
                    '30_day': round(total_30_day, 2),
                    '60_day': round(total_60_day, 2),
                    '90_day': round(total_90_day, 2)
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to generate cost forecast: {e}")
            return {'error': str(e)}
    
    def generate_roi_report(self) -> Dict:
        """Calculate ROI from optimization recommendations"""
        try:
            # Get idle resources (potential savings)
            idle_resources = self.cost_allocator.get_idle_resources()
            
            # Calculate potential savings
            monthly_savings = sum(r['monthly_waste'] for r in idle_resources)
            
            # Get current monthly cost
            current_costs = self.cost_allocator.get_team_costs(hours=24)
            monthly_cost = sum(team['total_cost'] for team in current_costs.values()) * 30
            
            # Calculate ROI metrics
            savings_percentage = (monthly_savings / monthly_cost * 100) if monthly_cost > 0 else 0
            annual_savings = monthly_savings * 12
            
            # Break down by optimization type
            optimization_breakdown = {
                'right_sizing': {
                    'opportunities': len(idle_resources),
                    'monthly_savings': round(monthly_savings, 2),
                    'annual_savings': round(annual_savings, 2)
                },
                'total': {
                    'monthly_savings': round(monthly_savings, 2),
                    'annual_savings': round(annual_savings, 2),
                    'savings_percentage': round(savings_percentage, 1)
                }
            }
            
            return {
                'generated_at': datetime.now().isoformat(),
                'current_monthly_cost': round(monthly_cost, 2),
                'potential_monthly_savings': round(monthly_savings, 2),
                'potential_annual_savings': round(annual_savings, 2),
                'savings_percentage': round(savings_percentage, 1),
                'optimization_breakdown': optimization_breakdown,
                'top_opportunities': idle_resources[:5]
            }
            
        except Exception as e:
            logger.error(f"Failed to generate ROI report: {e}")
            return {'error': str(e)}
    
    def generate_trend_analysis(self, days: int = 30) -> Dict:
        """Analyze trends in cost, performance, and scaling"""
        try:
            # Get cost trends
            cost_trends = self.cost_allocator.get_cost_trends(days=days)
            
            # Analyze trends
            if not cost_trends.get('trends') or len(cost_trends['trends']) < 2:
                return {'error': 'Insufficient data for trend analysis'}
            
            trends = cost_trends['trends']
            
            # Calculate week-over-week change
            if len(trends) >= 14:
                last_week = sum(t['total_cost'] for t in trends[-7:])
                prev_week = sum(t['total_cost'] for t in trends[-14:-7])
                wow_change = ((last_week - prev_week) / prev_week * 100) if prev_week > 0 else 0
            else:
                wow_change = 0
            
            # Calculate month-over-month (if enough data)
            if len(trends) >= 60:
                last_month = sum(t['total_cost'] for t in trends[-30:])
                prev_month = sum(t['total_cost'] for t in trends[-60:-30])
                mom_change = ((last_month - prev_month) / prev_month * 100) if prev_month > 0 else 0
            else:
                mom_change = 0
            
            return {
                'generated_at': datetime.now().isoformat(),
                'period_days': days,
                'cost_trends': {
                    'week_over_week_change': round(wow_change, 1),
                    'month_over_month_change': round(mom_change, 1),
                    'trend_direction': 'up' if wow_change > 5 else 'down' if wow_change < -5 else 'stable',
                    'daily_average': round(sum(t['total_cost'] for t in trends) / len(trends), 2)
                },
                'historical_data': trends
            }
            
        except Exception as e:
            logger.error(f"Failed to generate trend analysis: {e}")
            return {'error': str(e)}
    
    def _calculate_efficiency_score(self) -> int:
        """Calculate overall cluster efficiency score (0-100)"""
        try:
            idle_resources = self.cost_allocator.get_idle_resources()
            
            if not idle_resources:
                return 100
            
            # Calculate average utilization
            avg_cpu_util = sum(r['cpu_utilization'] for r in idle_resources) / len(idle_resources)
            avg_mem_util = sum(r['memory_utilization'] for r in idle_resources) / len(idle_resources)
            
            # Score based on utilization (higher is better)
            efficiency = (avg_cpu_util + avg_mem_util) / 2
            
            return min(100, max(0, int(efficiency)))
            
        except Exception as e:
            logger.warning(f"Failed to calculate efficiency score: {e}")
            return 0
    
    def _get_scaling_events(self, days: int) -> Dict:
        """Get scaling event statistics"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN new_replicas > old_replicas THEN 1 ELSE 0 END) as scale_ups,
                       SUM(CASE WHEN new_replicas < old_replicas THEN 1 ELSE 0 END) as scale_downs
                FROM scaling_events
                WHERE timestamp >= datetime('now', '-{} days')
            """.format(days))
            
            row = cursor.fetchone()
            if row:
                return {
                    'total': row[0] or 0,
                    'scale_ups': row[1] or 0,
                    'scale_downs': row[2] or 0
                }
            
        except Exception as e:
            logger.warning(f"Failed to get scaling events: {e}")
        
        return {'total': 0, 'scale_ups': 0, 'scale_downs': 0}
    
    def _get_deployment_metrics(self, namespace: str, deployment: str, days: int) -> Dict:
        """Get metrics for a specific deployment"""
        try:
            key = f"{namespace}/{deployment}"
            cursor = self.db.conn.cursor()
            
            cursor.execute("""
                SELECT AVG(cpu_usage), AVG(memory_usage), AVG(replicas),
                       MIN(replicas), MAX(replicas)
                FROM metrics
                WHERE deployment_key = ? AND timestamp >= datetime('now', '-{} days')
            """.format(days), (key,))
            
            row = cursor.fetchone()
            if row and row[0]:
                return {
                    'avg_cpu': round(row[0], 2),
                    'avg_memory': round(row[1], 2),
                    'avg_replicas': round(row[2], 1),
                    'min_replicas': row[3],
                    'max_replicas': row[4]
                }
            
        except Exception as e:
            logger.warning(f"Failed to get metrics for {namespace}/{deployment}: {e}")
        
        return {}
    
    def _generate_recommendations(self, idle_resources: List, anomalies: List) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if idle_resources:
            top_waste = idle_resources[0]
            recommendations.append(
                f"Right-size {top_waste['namespace']}/{top_waste['deployment']} "
                f"to save ${top_waste['monthly_waste']:.2f}/month "
                f"(currently {top_waste['cpu_utilization']}% CPU utilized)"
            )
        
        if len(idle_resources) > 5:
            total_waste = sum(r['monthly_waste'] for r in idle_resources[:5])
            recommendations.append(
                f"Review top 5 underutilized deployments for potential savings of ${total_waste:.2f}/month"
            )
        
        if anomalies:
            recommendations.append(
                f"Investigate {len(anomalies)} cost anomalies detected in the past week"
            )
        
        if not recommendations:
            recommendations.append("Cluster is well-optimized. Continue monitoring for changes.")
        
        return recommendations
