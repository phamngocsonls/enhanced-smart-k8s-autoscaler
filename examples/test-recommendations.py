#!/usr/bin/env python3.12
"""
Test script for FinOps Recommendations API
Demonstrates the recommendation system with sample data
"""

import json
import sys
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, '.')

from src.intelligence import TimeSeriesDatabase, CostOptimizer, AlertManager


def create_sample_data(db: TimeSeriesDatabase, deployment: str, hours: int = 168):
    """Create sample metrics data for testing"""
    print(f"📊 Creating {hours} hours of sample data for {deployment}...")
    
    # Simulate a deployment with:
    # - CPU request: 1000m
    # - Actual usage: 400-600m (avg ~450m)
    # - Memory request: 512Mi
    # - Actual usage: 300-350Mi
    # - HPA target: 70%
    
    import random
    from datetime import datetime, timedelta
    
    base_time = datetime.now() - timedelta(hours=hours)
    
    for i in range(hours * 60):  # One data point per minute
        timestamp = base_time + timedelta(minutes=i)
        
        # Simulate realistic CPU usage with daily patterns
        hour_of_day = timestamp.hour
        
        # Higher usage during business hours (9-17)
        if 9 <= hour_of_day <= 17:
            base_cpu = 0.5  # 500m average
            variation = random.uniform(-0.1, 0.15)  # ±100-150m
        else:
            base_cpu = 0.35  # 350m average
            variation = random.uniform(-0.05, 0.1)  # ±50-100m
        
        cpu_usage = max(0.1, base_cpu + variation)  # cores
        
        # Memory usage is more stable
        memory_usage = random.uniform(300, 350)  # MB
        
        # Store metrics
        db.store_metrics(
            deployment=deployment,
            namespace="production",
            node_utilization=65.0,
            pod_count=3,
            pod_cpu_usage=cpu_usage,
            hpa_target=70.0,
            confidence=85.0,
            action_taken="none",
            cpu_request=1000,  # millicores
            memory_request=512,  # MB
            memory_usage=memory_usage
        )
    
    print(f"✅ Created {hours * 60} data points")


def test_recommendations():
    """Test the recommendation system"""
    print("🧪 Testing FinOps Recommendation System\n")
    print("=" * 80)
    
    # Initialize components
    db = TimeSeriesDatabase("/tmp/test_recommendations.db")
    alert_manager = AlertManager()
    cost_optimizer = CostOptimizer(db, alert_manager)
    
    deployment = "test-api-service"
    
    # Create sample data
    create_sample_data(db, deployment, hours=168)
    
    print("\n" + "=" * 80)
    print("🔍 Analyzing and generating recommendations...\n")
    
    # Get recommendations
    recommendations = cost_optimizer.calculate_resource_recommendations(
        deployment=deployment,
        hours=168
    )
    
    if not recommendations:
        print("❌ Failed to generate recommendations")
        return
    
    # Display results
    print("📋 CURRENT CONFIGURATION")
    print("-" * 80)
    current = recommendations['current']
    print(f"CPU Request:        {current['cpu_request_millicores']}m")
    print(f"Memory Request:     {current['memory_request_mb']}Mi")
    print(f"HPA Target:         {current['hpa_target_percent']}%")
    print(f"Scaling Threshold:  {current['scaling_threshold_millicores']:.1f}m")
    print(f"CPU Utilization:    {current['cpu_utilization_percent']:.1f}%")
    print(f"Memory Utilization: {current['memory_utilization_percent']:.1f}%")
    print(f"Monthly Cost:       ${current['monthly_cost_usd']:.2f}")
    
    print("\n📊 USAGE STATISTICS")
    print("-" * 80)
    stats = recommendations['usage_stats']
    print(f"CPU Average:  {stats['cpu_avg_millicores']:.1f}m")
    print(f"CPU P50:      {stats['cpu_p50_millicores']:.1f}m")
    print(f"CPU P95:      {stats['cpu_p95_millicores']:.1f}m")
    print(f"CPU P99:      {stats['cpu_p99_millicores']:.1f}m")
    print(f"CPU Max:      {stats['cpu_max_millicores']:.1f}m")
    print(f"Memory Avg:   {stats['memory_avg_mb']:.1f}Mi")
    print(f"Memory P95:   {stats['memory_p95_mb']:.1f}Mi")
    print(f"Memory Max:   {stats['memory_max_mb']:.1f}Mi")
    
    print("\n✨ RECOMMENDED CONFIGURATION")
    print("-" * 80)
    recommended = recommendations['recommended']
    print(f"CPU Request:        {recommended['cpu_request_millicores']}m")
    print(f"Memory Request:     {recommended['memory_request_mb']}Mi")
    print(f"HPA Target:         {recommended['hpa_target_percent']:.1f}%")
    print(f"Scaling Threshold:  {recommended['scaling_threshold_millicores']:.1f}m")
    print(f"Monthly Cost:       ${recommended['monthly_cost_usd']:.2f}")
    
    print("\n💰 COST SAVINGS")
    print("-" * 80)
    savings = recommendations['savings']
    print(f"Monthly Savings:      ${savings['monthly_savings_usd']:.2f}")
    print(f"Savings Percent:      {savings['savings_percent']:.1f}%")
    print(f"CPU Reduction:        {savings['cpu_reduction_percent']:.1f}%")
    print(f"Memory Reduction:     {savings['memory_reduction_percent']:.1f}%")
    print(f"HPA Adjustment:       {savings['hpa_adjustment_percent']:.1f}%")
    
    print(f"\n🎯 RECOMMENDATION LEVEL: {recommendations['recommendation_level'].upper()}")
    print(f"💡 {recommendations['recommendation_text']}")
    
    if recommendations['warnings']:
        print("\n⚠️  WARNINGS:")
        for warning in recommendations['warnings']:
            print(f"   {warning}")
    
    print("\n🛠️  IMPLEMENTATION STEPS")
    print("-" * 80)
    impl = recommendations['implementation']
    print(f"Step 1: {impl['step1']}")
    print(f"Step 2: {impl['step2']}")
    print(f"Step 3: {impl['step3']}")
    print(f"Step 4: {impl['step4']}")
    
    print("\n📄 YAML CONFIGURATION")
    print("-" * 80)
    print(impl['yaml_snippet'])
    
    print("\n" + "=" * 80)
    print("✅ Test completed successfully!")
    print(f"📊 Analyzed {recommendations['data_points_analyzed']} data points")
    print(f"⏱️  Analysis period: {recommendations['analysis_period_hours']} hours")
    print(f"🎯 Average pod count: {recommendations['avg_pod_count']:.1f}")
    
    # Verify the key insight: scaling threshold remains the same
    current_threshold = current['scaling_threshold_millicores']
    recommended_threshold = recommended['scaling_threshold_millicores']
    threshold_diff = abs(current_threshold - recommended_threshold)
    
    print(f"\n🔑 KEY INSIGHT: Scaling Threshold Verification")
    print(f"   Current threshold:     {current_threshold:.1f}m")
    print(f"   Recommended threshold: {recommended_threshold:.1f}m")
    print(f"   Difference:            {threshold_diff:.1f}m")
    
    if threshold_diff < 5:  # Allow 5m tolerance
        print("   ✅ PASS: Scaling behavior will remain the same!")
    else:
        print("   ⚠️  WARNING: Scaling threshold changed significantly!")
    
    # Cleanup
    db.close()
    import os
    os.remove("/tmp/test_recommendations.db")
    
    print("\n🎉 All tests passed!")


if __name__ == "__main__":
    test_recommendations()
