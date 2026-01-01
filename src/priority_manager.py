"""
Priority-Based Scaling Manager
Intelligent resource orchestration based on workload priorities
"""

import logging
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class Priority(Enum):
    """Workload priority levels"""
    CRITICAL = "critical"  # Mission-critical (payment, auth)
    HIGH = "high"          # Important services (APIs)
    MEDIUM = "medium"      # Standard workloads (default)
    LOW = "low"            # Background jobs
    BEST_EFFORT = "best_effort"  # Can be paused


@dataclass
class PriorityConfig:
    """Priority-specific configuration"""
    level: Priority
    weight: float              # Processing order (1.0 = first)
    target_adjustment: int     # HPA target adjustment (%)
    scale_up_speed: float      # Scale up multiplier
    scale_down_speed: float    # Scale down multiplier
    min_headroom: int          # Minimum CPU headroom (%)
    can_preempt: bool          # Can scale down others
    can_be_preempted: bool     # Can be scaled down by others


# Priority configurations
PRIORITY_CONFIGS = {
    Priority.CRITICAL: PriorityConfig(
        level=Priority.CRITICAL,
        weight=1.0,
        target_adjustment=-15,      # 55% target (lots of headroom)
        scale_up_speed=2.0,         # Scale up 2x faster
        scale_down_speed=0.25,      # Scale down 4x slower
        min_headroom=30,            # Always keep 30% headroom
        can_preempt=True,           # Can force others to scale down
        can_be_preempted=False      # Never scaled down for others
    ),
    Priority.HIGH: PriorityConfig(
        level=Priority.HIGH,
        weight=0.8,
        target_adjustment=-10,      # 60% target (more headroom)
        scale_up_speed=1.5,         # Scale up 1.5x faster
        scale_down_speed=0.5,       # Scale down 2x slower
        min_headroom=20,
        can_preempt=True,
        can_be_preempted=False
    ),
    Priority.MEDIUM: PriorityConfig(
        level=Priority.MEDIUM,
        weight=0.5,
        target_adjustment=0,        # 70% target (normal)
        scale_up_speed=1.0,         # Normal speed
        scale_down_speed=1.0,       # Normal speed
        min_headroom=10,
        can_preempt=False,
        can_be_preempted=True
    ),
    Priority.LOW: PriorityConfig(
        level=Priority.LOW,
        weight=0.2,
        target_adjustment=10,       # 80% target (cost-optimized)
        scale_up_speed=0.5,         # Scale up 2x slower
        scale_down_speed=2.0,       # Scale down 2x faster
        min_headroom=5,
        can_preempt=False,
        can_be_preempted=True
    ),
    Priority.BEST_EFFORT: PriorityConfig(
        level=Priority.BEST_EFFORT,
        weight=0.1,
        target_adjustment=15,       # 85% target (very cost-optimized)
        scale_up_speed=0.25,        # Scale up 4x slower
        scale_down_speed=3.0,       # Scale down 3x faster
        min_headroom=0,
        can_preempt=False,
        can_be_preempted=True
    )
}


class PriorityManager:
    """
    Manages priority-based scaling decisions
    
    Smart features:
    - Automatic priority detection from labels/annotations
    - Resource pressure-aware adjustments
    - Preemptive scaling (high priority can scale down low priority)
    - Historical learning per priority
    - Cost optimization for low-priority workloads
    """
    
    def __init__(self, db):
        self.db = db
        self.deployment_priorities: Dict[str, Priority] = {}
        self.pressure_history: List[float] = []
        self.last_preemption = {}
        
    def set_priority(self, deployment: str, priority: str):
        """Set priority for a deployment"""
        try:
            priority_enum = Priority(priority.lower())
            self.deployment_priorities[deployment] = priority_enum
            logger.info(f"{deployment} - Priority set to {priority_enum.value}")
        except ValueError:
            logger.warning(f"{deployment} - Invalid priority '{priority}', using MEDIUM")
            self.deployment_priorities[deployment] = Priority.MEDIUM
    
    def get_priority(self, deployment: str) -> Priority:
        """Get priority for a deployment (default: MEDIUM)"""
        return self.deployment_priorities.get(deployment, Priority.MEDIUM)
    
    def get_config(self, deployment: str) -> PriorityConfig:
        """Get priority configuration for a deployment"""
        priority = self.get_priority(deployment)
        return PRIORITY_CONFIGS[priority]
    
    def sort_deployments_by_priority(self, deployments: List[Dict]) -> List[Dict]:
        """
        Sort deployments by priority (highest first)
        
        Smart: During pressure, process high-priority first to protect them
        """
        def get_weight(dep):
            deployment_name = dep.get('deployment', '')
            config = self.get_config(deployment_name)
            return config.weight
        
        return sorted(deployments, key=get_weight, reverse=True)
    
    def calculate_target_adjustment(
        self, 
        deployment: str, 
        base_target: int,
        node_pressure: float,
        cluster_pressure: float
    ) -> int:
        """
        Calculate smart HPA target based on priority and pressure
        
        Smart features:
        - Adjusts based on priority
        - Considers node AND cluster pressure
        - More aggressive during high pressure
        - Learns from historical pressure patterns
        """
        config = self.get_config(deployment)
        
        # Base adjustment from priority
        adjustment = config.target_adjustment
        
        # Track pressure history (last 10 readings)
        self.pressure_history.append(max(node_pressure, cluster_pressure))
        if len(self.pressure_history) > 10:
            self.pressure_history.pop(0)
        
        avg_pressure = sum(self.pressure_history) / len(self.pressure_history)
        
        # Smart pressure-based adjustments
        if avg_pressure > 85:  # CRITICAL pressure
            if config.level in [Priority.CRITICAL, Priority.HIGH]:
                adjustment -= 10  # Give MORE headroom to critical
            elif config.level in [Priority.LOW, Priority.BEST_EFFORT]:
                adjustment += 15  # Force low-priority to use LESS
        
        elif avg_pressure > 75:  # HIGH pressure
            if config.level == Priority.CRITICAL:
                adjustment -= 5
            elif config.level in [Priority.LOW, Priority.BEST_EFFORT]:
                adjustment += 10
        
        elif avg_pressure < 40:  # LOW pressure - optimize costs
            if config.level in [Priority.LOW, Priority.BEST_EFFORT]:
                adjustment += 5  # Low-priority can use even less
        
        # Apply adjustment
        new_target = base_target + adjustment
        
        # Ensure minimum headroom
        min_target = 100 - config.min_headroom
        new_target = min(new_target, min_target)
        
        # Bounds check
        new_target = max(30, min(95, new_target))
        
        logger.debug(
            f"{deployment} - Priority: {config.level.value}, "
            f"Base: {base_target}%, Adjustment: {adjustment:+d}%, "
            f"Final: {new_target}%, Pressure: {avg_pressure:.1f}%"
        )
        
        return new_target
    
    def should_preempt(
        self,
        requesting_deployment: str,
        target_deployment: str,
        cluster_pressure: float
    ) -> bool:
        """
        Determine if high-priority workload can preempt low-priority
        
        Smart: Only preempt when:
        - Cluster pressure is high (>80%)
        - Requesting deployment has higher priority
        - Target can be preempted
        - Haven't preempted recently (cooldown)
        """
        if cluster_pressure < 80:
            return False  # Only preempt during pressure
        
        requesting_config = self.get_config(requesting_deployment)
        target_config = self.get_config(target_deployment)
        
        # Check if preemption is allowed
        if not requesting_config.can_preempt:
            return False
        if not target_config.can_be_preempted:
            return False
        
        # Check priority difference
        if requesting_config.weight <= target_config.weight:
            return False  # Must be higher priority
        
        # Check cooldown (don't preempt same deployment within 5 minutes)
        key = f"{requesting_deployment}->{target_deployment}"
        last_time = self.last_preemption.get(key)
        if last_time and datetime.now() - last_time < timedelta(minutes=5):
            return False
        
        # Allow preemption
        self.last_preemption[key] = datetime.now()
        logger.info(
            f"PREEMPTION: {requesting_deployment} ({requesting_config.level.value}) "
            f"can scale down {target_deployment} ({target_config.level.value})"
        )
        return True
    
    def get_scale_speed_multiplier(
        self,
        deployment: str,
        direction: str  # 'up' or 'down'
    ) -> float:
        """
        Get scaling speed multiplier based on priority
        
        Smart: High-priority scales up faster, down slower
        """
        config = self.get_config(deployment)
        
        if direction == 'up':
            return config.scale_up_speed
        else:
            return config.scale_down_speed
    
    def get_priority_stats(self) -> Dict:
        """Get statistics by priority level"""
        stats = {}
        
        for priority in Priority:
            deployments = [
                dep for dep, pri in self.deployment_priorities.items()
                if pri == priority
            ]
            
            stats[priority.value] = {
                'count': len(deployments),
                'deployments': deployments,
                'config': {
                    'target_adjustment': PRIORITY_CONFIGS[priority].target_adjustment,
                    'scale_up_speed': PRIORITY_CONFIGS[priority].scale_up_speed,
                    'scale_down_speed': PRIORITY_CONFIGS[priority].scale_down_speed,
                    'can_preempt': PRIORITY_CONFIGS[priority].can_preempt
                }
            }
        
        return stats
    
    def auto_detect_priority(self, deployment_name: str, labels: Dict, annotations: Dict) -> Priority:
        """
        Smart auto-detection of priority from deployment metadata
        
        Checks:
        - Explicit priority label/annotation
        - Service type keywords
        - Namespace patterns
        """
        # Check explicit priority
        priority_str = (
            labels.get('priority') or
            labels.get('workload-priority') or
            annotations.get('autoscaler.k8s.io/priority') or
            annotations.get('priority')
        )
        
        if priority_str:
            try:
                return Priority(priority_str.lower())
            except ValueError:
                pass
        
        # Auto-detect from name patterns
        name_lower = deployment_name.lower()
        
        if any(keyword in name_lower for keyword in ['payment', 'auth', 'billing', 'checkout']):
            return Priority.CRITICAL
        
        if any(keyword in name_lower for keyword in ['api', 'gateway', 'frontend', 'web']):
            return Priority.HIGH
        
        if any(keyword in name_lower for keyword in ['worker', 'job', 'batch', 'cron']):
            return Priority.LOW
        
        if any(keyword in name_lower for keyword in ['report', 'analytics', 'backup', 'cleanup']):
            return Priority.BEST_EFFORT
        
        # Default
        return Priority.MEDIUM
