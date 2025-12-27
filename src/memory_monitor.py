"""
Memory Monitor and OOM Prevention
Monitors memory usage and prevents OOM kills
"""

import logging
import os
import psutil
import gc
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


class MemoryMonitor:
    """Monitor memory usage and prevent OOM"""
    
    def __init__(
        self,
        warning_threshold: float = 0.75,  # 75% of limit
        critical_threshold: float = 0.90,  # 90% of limit
        check_interval: int = 30,  # Check every 30 seconds
        memory_limit_mb: Optional[int] = None
    ):
        """
        Initialize memory monitor
        
        Args:
            warning_threshold: Memory usage threshold for warnings (0.0-1.0)
            critical_threshold: Memory usage threshold for critical actions (0.0-1.0)
            check_interval: How often to check memory (seconds)
            memory_limit_mb: Memory limit in MB (None = auto-detect from cgroups)
        """
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.check_interval = check_interval
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # Get memory limit
        if memory_limit_mb is None:
            self.memory_limit_mb = self._get_memory_limit()
        else:
            self.memory_limit_mb = memory_limit_mb
        
        # Get process
        self.process = psutil.Process(os.getpid())
        
        logger.info(
            f"Memory monitor initialized: limit={self.memory_limit_mb}MB, "
            f"warning={warning_threshold*100:.0f}%, critical={critical_threshold*100:.0f}%"
        )
    
    def _get_memory_limit(self) -> int:
        """Get memory limit from cgroups or system"""
        try:
            # Try to read from cgroups v2
            cgroup_path = "/sys/fs/cgroup/memory.max"
            if os.path.exists(cgroup_path):
                with open(cgroup_path, 'r') as f:
                    limit = f.read().strip()
                    if limit.isdigit():
                        return int(limit) // (1024 * 1024)  # Convert to MB
            
            # Try cgroups v1
            cgroup_path = "/sys/fs/cgroup/memory/memory.limit_in_bytes"
            if os.path.exists(cgroup_path):
                with open(cgroup_path, 'r') as f:
                    limit = f.read().strip()
                    if limit.isdigit() and int(limit) > 0:
                        return int(limit) // (1024 * 1024)  # Convert to MB
            
            # Fallback: Use system memory
            total_memory = psutil.virtual_memory().total // (1024 * 1024)
            logger.warning(f"Could not read cgroup limit, using system memory: {total_memory}MB")
            return total_memory
        except Exception as e:
            logger.warning(f"Error reading memory limit: {e}, using default 1024MB")
            return 1024  # Default 1GB
    
    def get_memory_usage(self) -> dict:
        """Get current memory usage statistics"""
        try:
            process_memory = self.process.memory_info()
            memory_mb = process_memory.rss / (1024 * 1024)
            memory_percent = (memory_mb / self.memory_limit_mb) * 100 if self.memory_limit_mb > 0 else 0
            
            return {
                'memory_mb': round(memory_mb, 2),
                'memory_limit_mb': self.memory_limit_mb,
                'memory_percent': round(memory_percent, 2),
                'available_mb': round(self.memory_limit_mb - memory_mb, 2),
                'status': self._get_status(memory_percent / 100.0)
            }
        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return {
                'memory_mb': 0,
                'memory_limit_mb': self.memory_limit_mb,
                'memory_percent': 0,
                'available_mb': self.memory_limit_mb,
                'status': 'unknown'
            }
    
    def _get_status(self, usage_ratio: float) -> str:
        """Get status based on usage ratio"""
        if usage_ratio >= self.critical_threshold:
            return 'critical'
        elif usage_ratio >= self.warning_threshold:
            return 'warning'
        else:
            return 'normal'
    
    def _free_memory(self):
        """Free memory by forcing garbage collection"""
        logger.info("Forcing garbage collection to free memory")
        collected = gc.collect()
        logger.info(f"Garbage collection freed {collected} objects")
    
    def check_and_act(self) -> dict:
        """Check memory and take action if needed"""
        usage = self.get_memory_usage()
        usage_ratio = usage['memory_percent'] / 100.0
        
        if usage_ratio >= self.critical_threshold:
            logger.critical(
                f"Memory usage critical: {usage['memory_mb']:.1f}MB / {usage['memory_limit_mb']}MB "
                f"({usage['memory_percent']:.1f}%) - Taking action"
            )
            self._free_memory()
            # Re-check after cleanup
            usage = self.get_memory_usage()
            usage_ratio = usage['memory_percent'] / 100.0
            
            if usage_ratio >= self.critical_threshold:
                logger.error(
                    f"Memory still critical after cleanup: {usage['memory_percent']:.1f}% - "
                    "Consider reducing workload or increasing memory limit"
                )
        elif usage_ratio >= self.warning_threshold:
            logger.warning(
                f"Memory usage high: {usage['memory_mb']:.1f}MB / {usage['memory_limit_mb']}MB "
                f"({usage['memory_percent']:.1f}%)"
            )
        
        return usage
    
    def start_monitoring(self):
        """Start background memory monitoring"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="memory-monitor"
        )
        self.monitor_thread.start()
        logger.info("Memory monitoring started")
    
    def stop_monitoring(self):
        """Stop background memory monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Memory monitoring stopped")
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        while self.monitoring:
            try:
                self.check_and_act()
            except Exception as e:
                logger.error(f"Error in memory monitor loop: {e}")
            
            # Sleep with interruption check
            for _ in range(self.check_interval):
                if not self.monitoring:
                    break
                time.sleep(1)

