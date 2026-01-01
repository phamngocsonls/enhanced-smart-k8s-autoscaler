#!/usr/bin/env python3
"""
Priority-Based Scaling Demo
Demonstrates the priority manager functionality
"""

import sys
sys.path.insert(0, '.')

from src.priority_manager import PriorityManager, Priority
from unittest.mock import Mock


def print_section(title):
    """Print section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def demo_priority_levels():
    """Demonstrate priority levels and configurations"""
    print_section("Priority Levels & Configurations")
    
    db = Mock()
    pm = PriorityManager(db)
    
    priorities = ['critical', 'high', 'medium', 'low', 'best_effort']
    
    print(f"{'Priority':<15} {'Target Adj':<12} {'Scale Up':<10} {'Scale Down':<12} {'Can Preempt':<12}")
    print("-" * 70)
    
    for priority in priorities:
        pm.set_priority("test", priority)
        config = pm.get_config("test")
        
        print(f"{priority:<15} {config.target_adjustment:+d}% ({70+config.target_adjustment}%)"
              f"    {config.scale_up_speed}x"
              f"        {config.scale_down_speed}x"
              f"          {'Yes' if config.can_preempt else 'No'}")


def demo_sorting():
    """Demonstrate deployment sorting by priority"""
    print_section("Deployment Processing Order")
    
    db = Mock()
    pm = PriorityManager(db)
    
    # Set priorities
    pm.set_priority("payment-service", "critical")
    pm.set_priority("api-gateway", "high")
    pm.set_priority("web-app", "medium")
    pm.set_priority("email-worker", "low")
    pm.set_priority("analytics-job", "best_effort")
    
    deployments = [
        {'deployment': 'email-worker'},
        {'deployment': 'payment-service'},
        {'deployment': 'analytics-job'},
        {'deployment': 'web-app'},
        {'deployment': 'api-gateway'}
    ]
    
    sorted_deps = pm.sort_deployments_by_priority(deployments)
    
    print("Processing order (highest priority first):\n")
    for i, dep in enumerate(sorted_deps, 1):
        name = dep['deployment']
        priority = pm.get_priority(name)
        print(f"  {i}. {name:<25} [{priority.value}]")


def demo_target_adjustment():
    """Demonstrate target adjustment under different pressures"""
    print_section("HPA Target Adjustments Under Pressure")
    
    db = Mock()
    pm = PriorityManager(db)
    
    pm.set_priority("critical-service", "critical")
    pm.set_priority("high-service", "high")
    pm.set_priority("medium-service", "medium")
    pm.set_priority("low-service", "low")
    
    base_target = 70
    pressures = [
        ("Low (30%)", 30.0),
        ("Normal (50%)", 50.0),
        ("High (75%)", 75.0),
        ("Critical (90%)", 90.0)
    ]
    
    print(f"Base HPA Target: {base_target}%\n")
    print(f"{'Pressure':<20} {'Critical':<12} {'High':<12} {'Medium':<12} {'Low':<12}")
    print("-" * 70)
    
    for pressure_name, pressure in pressures:
        critical = pm.calculate_target_adjustment("critical-service", base_target, pressure, pressure)
        high = pm.calculate_target_adjustment("high-service", base_target, pressure, pressure)
        medium = pm.calculate_target_adjustment("medium-service", base_target, pressure, pressure)
        low = pm.calculate_target_adjustment("low-service", base_target, pressure, pressure)
        
        print(f"{pressure_name:<20} {critical}%"
              f"         {high}%"
              f"         {medium}%"
              f"         {low}%")


def demo_preemption():
    """Demonstrate preemption logic"""
    print_section("Preemption Scenarios")
    
    db = Mock()
    pm = PriorityManager(db)
    
    pm.set_priority("critical-service", "critical")
    pm.set_priority("high-service", "high")
    pm.set_priority("low-service", "low")
    
    scenarios = [
        ("Critical → Low", "critical-service", "low-service", 90.0),
        ("Critical → Low", "critical-service", "low-service", 50.0),
        ("High → Low", "high-service", "low-service", 85.0),
        ("Low → Critical", "low-service", "critical-service", 90.0),
        ("High → High", "high-service", "high-service", 90.0),
    ]
    
    print(f"{'Scenario':<20} {'Pressure':<12} {'Can Preempt?':<15} {'Reason'}")
    print("-" * 70)
    
    for name, requesting, target, pressure in scenarios:
        can_preempt = pm.should_preempt(requesting, target, pressure)
        
        if pressure < 80:
            reason = "Pressure too low"
        elif requesting == target:
            reason = "Same deployment"
        elif not can_preempt:
            req_config = pm.get_config(requesting)
            tgt_config = pm.get_config(target)
            if req_config.weight <= tgt_config.weight:
                reason = "Insufficient priority"
            elif not tgt_config.can_be_preempted:
                reason = "Target protected"
            else:
                reason = "Cannot preempt"
        else:
            reason = "Allowed"
        
        print(f"{name:<20} {pressure:.0f}%"
              f"         {'✓ Yes' if can_preempt else '✗ No':<15} {reason}")


def demo_auto_detection():
    """Demonstrate auto-detection of priorities"""
    print_section("Auto-Detection from Deployment Names")
    
    db = Mock()
    pm = PriorityManager(db)
    
    deployments = [
        "payment-service",
        "auth-api",
        "api-gateway",
        "web-frontend",
        "email-worker",
        "batch-job",
        "analytics-report",
        "backup-service",
        "random-app"
    ]
    
    print(f"{'Deployment Name':<25} {'Detected Priority':<20} {'Reason'}")
    print("-" * 70)
    
    for name in deployments:
        priority = pm.auto_detect_priority(name, {}, {})
        
        if 'payment' in name or 'auth' in name:
            reason = "Critical keyword"
        elif 'api' in name or 'web' in name or 'frontend' in name:
            reason = "High priority keyword"
        elif 'worker' in name or 'job' in name or 'batch' in name:
            reason = "Low priority keyword"
        elif 'report' in name or 'analytics' in name or 'backup' in name:
            reason = "Best-effort keyword"
        else:
            reason = "Default"
        
        print(f"{name:<25} {priority.value:<20} {reason}")


def demo_scale_speeds():
    """Demonstrate scale speed multipliers"""
    print_section("Scale Speed Multipliers")
    
    db = Mock()
    pm = PriorityManager(db)
    
    priorities = ['critical', 'high', 'medium', 'low', 'best_effort']
    
    print(f"{'Priority':<15} {'Scale Up Speed':<20} {'Scale Down Speed':<20} {'Behavior'}")
    print("-" * 80)
    
    for priority in priorities:
        pm.set_priority("test", priority)
        up_speed = pm.get_scale_speed_multiplier("test", "up")
        down_speed = pm.get_scale_speed_multiplier("test", "down")
        
        if up_speed > 1.0:
            behavior = "Fast scale up, slow scale down"
        elif up_speed < 1.0:
            behavior = "Slow scale up, fast scale down"
        else:
            behavior = "Normal speed"
        
        print(f"{priority:<15} {up_speed}x"
              f"                 {down_speed}x"
              f"                 {behavior}")


def main():
    """Run all demos"""
    print("\n" + "="*60)
    print("  SMART AUTOSCALER - PRIORITY-BASED SCALING DEMO")
    print("  Version 0.0.10")
    print("="*60)
    
    demo_priority_levels()
    demo_sorting()
    demo_target_adjustment()
    demo_preemption()
    demo_auto_detection()
    demo_scale_speeds()
    
    print("\n" + "="*60)
    print("  Demo Complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
