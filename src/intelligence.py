"""
Intelligence Layer for Smart Autoscaler
Historical learning, predictions, anomaly detection, cost optimization
"""

import os
import sqlite3
import logging
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import statistics
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MetricsSnapshot:
    """Single point-in-time metrics snapshot"""
    timestamp: datetime
    deployment: str
    namespace: str
    node_utilization: float
    pod_count: int
    pod_cpu_usage: float
    hpa_target: int
    confidence: float
    scheduling_spike: bool
    action_taken: str
    cpu_request: int
    memory_request: int  # in MB
    memory_usage: float  # in MB
    node_selector: str


@dataclass
class CostMetrics:
    """Cost-related metrics"""
    deployment: str
    avg_pod_count: float
    avg_utilization: float
    wasted_capacity_percent: float
    estimated_monthly_cost: float
    optimization_potential: float
    recommendation: str
    # Detailed cost breakdown
    cpu_cost: float = 0.0
    memory_cost: float = 0.0
    total_cost: float = 0.0
    wasted_cpu_cost: float = 0.0
    wasted_memory_cost: float = 0.0
    total_wasted_cost: float = 0.0
    cpu_utilization_percent: float = 0.0
    memory_utilization_percent: float = 0.0
    runtime_hours: float = 0.0


@dataclass
class AnomalyAlert:
    """Anomaly detection alert"""
    timestamp: datetime
    deployment: str
    anomaly_type: str
    severity: str
    description: str
    current_value: float
    expected_value: float
    deviation_percent: float


@dataclass
class Prediction:
    """Scaling prediction"""
    timestamp: datetime
    deployment: str
    predicted_cpu: float
    confidence: float
    recommended_action: str
    reasoning: str


class TimeSeriesDatabase:
    """SQLite-based time-series database with auto-cleanup and self-healing"""
    
    def __init__(self, db_path: str = "/data/autoscaler.db"):
        self.db_path = db_path
        self.data_dir = str(Path(db_path).parent)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Retention settings (configurable via environment)
        self.metrics_retention_days = int(os.getenv('METRICS_RETENTION_DAYS', '30'))
        self.predictions_retention_days = int(os.getenv('PREDICTIONS_RETENTION_DAYS', '30'))
        self.anomalies_retention_days = int(os.getenv('ANOMALIES_RETENTION_DAYS', '90'))
        self.cleanup_interval_hours = int(os.getenv('DB_CLEANUP_INTERVAL_HOURS', '6'))
        
        # Disk space thresholds for auto-healing
        self.disk_warning_threshold = float(os.getenv('DISK_WARNING_THRESHOLD', '0.80'))  # 80%
        self.disk_critical_threshold = float(os.getenv('DISK_CRITICAL_THRESHOLD', '0.90'))  # 90%
        self.disk_emergency_threshold = float(os.getenv('DISK_EMERGENCY_THRESHOLD', '0.95'))  # 95%
        
        # Track last cleanup time
        self._last_cleanup = datetime.now()
        self._last_disk_check = datetime.now()
        self._disk_check_interval_minutes = 5  # Check disk every 5 minutes
        
        # Enable WAL mode for better concurrency and performance
        self.conn = sqlite3.connect(
            db_path, 
            check_same_thread=False,
            timeout=30.0  # Connection timeout
        )
        # Optimize SQLite settings
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")  # Balance safety/speed
        self.conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=30000")  # 30s busy timeout
        
        self._init_schema()
        self._migrate_schema()  # Migrate existing databases
        self._cleanup_old_data()
        
        # Initial disk check
        disk_usage = self._get_disk_usage()
        logger.info(
            f"Database initialized: retention={self.metrics_retention_days}d metrics, "
            f"{self.predictions_retention_days}d predictions, {self.anomalies_retention_days}d anomalies, "
            f"disk={disk_usage['percent']:.1f}% used"
        )
    
    def _get_disk_usage(self) -> dict:
        """
        Get disk usage for the data directory.
        Works with PVC in Kubernetes or local filesystem.
        
        Returns:
            Dict with total, used, free (bytes) and percent used
        """
        try:
            import shutil
            total, used, free = shutil.disk_usage(self.data_dir)
            percent = used / total if total > 0 else 0
            
            return {
                'total': total,
                'used': used,
                'free': free,
                'percent': percent,
                'total_gb': total / (1024**3),
                'used_gb': used / (1024**3),
                'free_gb': free / (1024**3)
            }
        except Exception as e:
            logger.warning(f"Error getting disk usage: {e}")
            return {
                'total': 0,
                'used': 0,
                'free': 0,
                'percent': 0,
                'total_gb': 0,
                'used_gb': 0,
                'free_gb': 0
            }
    
    def _check_disk_and_heal(self) -> bool:
        """
        Check disk usage and trigger auto-healing if needed.
        
        Returns:
            True if emergency cleanup was triggered
        """
        # Only check every few minutes to avoid overhead
        minutes_since_check = (datetime.now() - self._last_disk_check).total_seconds() / 60
        if minutes_since_check < self._disk_check_interval_minutes:
            return False
        
        self._last_disk_check = datetime.now()
        disk = self._get_disk_usage()
        
        if disk['percent'] >= self.disk_emergency_threshold:
            # EMERGENCY: 95%+ - Aggressive cleanup
            logger.warning(
                f"🚨 DISK EMERGENCY: {disk['percent']:.1f}% used ({disk['free_gb']:.2f}GB free). "
                f"Triggering aggressive auto-healing..."
            )
            self._emergency_cleanup()
            return True
            
        elif disk['percent'] >= self.disk_critical_threshold:
            # CRITICAL: 90%+ - Reduce retention and cleanup
            logger.warning(
                f"⚠️ DISK CRITICAL: {disk['percent']:.1f}% used ({disk['free_gb']:.2f}GB free). "
                f"Reducing retention and cleaning up..."
            )
            self._critical_cleanup()
            return True
            
        elif disk['percent'] >= self.disk_warning_threshold:
            # WARNING: 80%+ - Just log warning
            logger.warning(
                f"📊 DISK WARNING: {disk['percent']:.1f}% used ({disk['free_gb']:.2f}GB free). "
                f"Consider increasing PVC size or reducing retention."
            )
        
        return False
    
    def _emergency_cleanup(self):
        """
        Emergency cleanup when disk is at 95%+.
        Smart cleanup that preserves prediction patterns.
        """
        try:
            logger.warning("🧹 EMERGENCY CLEANUP: Starting smart cleanup to preserve prediction patterns...")
            
            # Step 1: Downsample old metrics (keep hourly averages instead of all data points)
            deleted_metrics = self._smart_downsample_metrics(keep_days=7, sample_interval_hours=1)
            
            # Step 2: Delete duplicate/redundant predictions (keep best per hour)
            deleted_predictions = self._cleanup_redundant_predictions(keep_days=14)
            
            # Step 3: Delete old anomalies (less critical for predictions)
            cursor = self.conn.execute("""
                DELETE FROM anomalies 
                WHERE timestamp < datetime('now', '-14 days')
            """)
            deleted_anomalies = cursor.rowcount
            
            self.conn.commit()
            
            logger.warning(
                f"🧹 EMERGENCY CLEANUP: Downsampled {deleted_metrics} metrics, "
                f"cleaned {deleted_predictions} predictions, deleted {deleted_anomalies} anomalies"
            )
            
            # Step 4: Check if still critical - if so, more aggressive but still smart
            disk = self._get_disk_usage()
            if disk['percent'] >= self.disk_critical_threshold:
                logger.warning("Disk still critical. Running aggressive smart cleanup...")
                self._aggressive_smart_cleanup()
            
            # Step 5: VACUUM to reclaim space
            logger.info("Running VACUUM to reclaim disk space...")
            self.conn.execute("VACUUM")
            self.conn.commit()
            
            # Log new disk usage
            disk = self._get_disk_usage()
            logger.info(f"✅ After emergency cleanup: {disk['percent']:.1f}% used ({disk['free_gb']:.2f}GB free)")
            
        except Exception as e:
            logger.error(f"Error during emergency cleanup: {e}")
    
    def _critical_cleanup(self):
        """
        Critical cleanup when disk is at 90%+.
        Smart cleanup that preserves prediction patterns.
        """
        try:
            logger.warning("🧹 CRITICAL CLEANUP: Starting smart cleanup to preserve prediction patterns...")
            
            # Step 1: Downsample old metrics (keep 2-hourly averages for data older than 14 days)
            deleted_metrics = self._smart_downsample_metrics(keep_days=14, sample_interval_hours=2)
            
            # Step 2: Clean redundant predictions
            deleted_predictions = self._cleanup_redundant_predictions(keep_days=21)
            
            # Step 3: Delete old anomalies
            cursor = self.conn.execute("""
                DELETE FROM anomalies 
                WHERE timestamp < datetime('now', '-30 days')
            """)
            deleted_anomalies = cursor.rowcount
            
            self.conn.commit()
            
            logger.warning(
                f"🧹 CRITICAL CLEANUP: Downsampled {deleted_metrics} metrics, "
                f"cleaned {deleted_predictions} predictions, deleted {deleted_anomalies} anomalies"
            )
            
            # VACUUM if significant data deleted
            if deleted_metrics > 500 or deleted_predictions > 100:
                logger.info("Running VACUUM to reclaim disk space...")
                self.conn.execute("VACUUM")
                self.conn.commit()
            
            # Log new disk usage
            disk = self._get_disk_usage()
            logger.info(f"✅ After critical cleanup: {disk['percent']:.1f}% used ({disk['free_gb']:.2f}GB free)")
            
        except Exception as e:
            logger.error(f"Error during critical cleanup: {e}")
    
    def _smart_downsample_metrics(self, keep_days: int, sample_interval_hours: int) -> int:
        """
        Smart downsampling: Keep recent data granular, aggregate older data.
        Preserves hourly patterns for predictions.
        
        Args:
            keep_days: Keep full granularity for this many days
            sample_interval_hours: For older data, keep one sample per this interval
        
        Returns:
            Number of rows deleted
        """
        try:
            # Get count before
            count_before = self.conn.execute("SELECT COUNT(*) FROM metrics_history").fetchone()[0]
            
            # For data older than keep_days, keep only one sample per interval per deployment
            # This preserves the pattern while reducing data volume
            
            # Step 1: Create temp table with downsampled data
            self.conn.execute("""
                CREATE TEMP TABLE IF NOT EXISTS metrics_to_keep AS
                SELECT 
                    MIN(id) as id,
                    deployment,
                    namespace,
                    strftime('%Y-%m-%d %H:00:00', timestamp) as hour_bucket,
                    AVG(node_utilization) as node_utilization,
                    ROUND(AVG(pod_count)) as pod_count,
                    AVG(pod_cpu_usage) as pod_cpu_usage,
                    ROUND(AVG(hpa_target)) as hpa_target,
                    AVG(confidence) as confidence,
                    MAX(action_taken) as action_taken,
                    AVG(cpu_request) as cpu_request,
                    AVG(memory_request) as memory_request,
                    AVG(memory_usage) as memory_usage
                FROM metrics_history
                WHERE timestamp < datetime('now', '-' || ? || ' days')
                GROUP BY deployment, namespace, 
                    strftime('%Y-%m-%d', timestamp),
                    CAST(strftime('%H', timestamp) / ? AS INTEGER) * ?
            """, (keep_days, sample_interval_hours, sample_interval_hours))
            
            # Step 2: Delete old granular data (but keep the downsampled representatives)
            # Keep IDs that are in our temp table
            cursor = self.conn.execute("""
                DELETE FROM metrics_history 
                WHERE timestamp < datetime('now', '-' || ? || ' days')
                AND id NOT IN (SELECT id FROM metrics_to_keep)
            """, (keep_days,))
            deleted = cursor.rowcount
            
            # Step 3: Drop temp table
            self.conn.execute("DROP TABLE IF EXISTS metrics_to_keep")
            
            self.conn.commit()
            
            count_after = self.conn.execute("SELECT COUNT(*) FROM metrics_history").fetchone()[0]
            logger.info(f"Smart downsample: {count_before} → {count_after} metrics (deleted {deleted})")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Error during smart downsample: {e}")
            self.conn.execute("DROP TABLE IF EXISTS metrics_to_keep")
            return 0
    
    def _cleanup_redundant_predictions(self, keep_days: int) -> int:
        """
        Clean up redundant predictions while keeping useful ones.
        Keeps: validated predictions, high-confidence predictions, one per hour.
        
        Args:
            keep_days: Keep all predictions for this many days
        
        Returns:
            Number of rows deleted
        """
        try:
            # Delete old predictions but keep:
            # 1. Validated predictions (useful for accuracy tracking)
            # 2. One prediction per hour per deployment (for pattern analysis)
            cursor = self.conn.execute("""
                DELETE FROM predictions 
                WHERE timestamp < datetime('now', '-' || ? || ' days')
                AND validated = 0
                AND rowid NOT IN (
                    SELECT MIN(rowid) 
                    FROM predictions 
                    WHERE timestamp < datetime('now', '-' || ? || ' days')
                    GROUP BY deployment, strftime('%Y-%m-%d %H', timestamp)
                )
            """, (keep_days, keep_days))
            
            deleted = cursor.rowcount
            self.conn.commit()
            
            return deleted
            
        except Exception as e:
            logger.error(f"Error cleaning predictions: {e}")
            return 0
    
    def _aggressive_smart_cleanup(self):
        """
        More aggressive cleanup but still preserves weekly patterns.
        Keeps at least 1 sample per hour per day-of-week (168 minimum).
        """
        try:
            # For each deployment, keep representative samples for each hour of each day-of-week
            # This ensures we have data for pattern recognition (168 slots = 7 days * 24 hours)
            
            # Step 1: Identify deployments
            deployments = self.conn.execute(
                "SELECT DISTINCT deployment FROM metrics_history"
            ).fetchall()
            
            total_deleted = 0
            
            for (deployment,) in deployments:
                # Keep best sample for each (day_of_week, hour) combination
                # Plus all data from last 3 days for recent patterns
                cursor = self.conn.execute("""
                    DELETE FROM metrics_history 
                    WHERE deployment = ?
                    AND timestamp < datetime('now', '-3 days')
                    AND id NOT IN (
                        -- Keep one representative per (day_of_week, hour) for weekly pattern
                        SELECT id FROM (
                            SELECT id, 
                                ROW_NUMBER() OVER (
                                    PARTITION BY strftime('%w', timestamp), strftime('%H', timestamp)
                                    ORDER BY timestamp DESC
                                ) as rn
                            FROM metrics_history
                            WHERE deployment = ?
                        ) WHERE rn <= 4  -- Keep 4 samples per slot for robustness
                    )
                """, (deployment, deployment))
                total_deleted += cursor.rowcount
            
            self.conn.commit()
            logger.warning(f"🧹 AGGRESSIVE SMART CLEANUP: Deleted {total_deleted} metrics while preserving weekly patterns")
            
        except Exception as e:
            logger.error(f"Error during aggressive smart cleanup: {e}")
    
    def _migrate_schema(self):
        """Migrate existing database schema to add new columns/tables"""
        try:
            # Check if predictions table has new columns
            cursor = self.conn.execute("PRAGMA table_info(predictions)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Add new columns to predictions table if they don't exist
            if 'actual_cpu' not in columns:
                logger.info("Migrating predictions table: adding actual_cpu column")
                self.conn.execute("ALTER TABLE predictions ADD COLUMN actual_cpu REAL")
            
            if 'validated' not in columns:
                logger.info("Migrating predictions table: adding validated column")
                self.conn.execute("ALTER TABLE predictions ADD COLUMN validated BOOLEAN DEFAULT 0")
            
            if 'accuracy' not in columns:
                logger.info("Migrating predictions table: adding accuracy column")
                self.conn.execute("ALTER TABLE predictions ADD COLUMN accuracy REAL")
            
            # Check if prediction_accuracy table exists
            cursor = self.conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='prediction_accuracy'
            """)
            if not cursor.fetchone():
                logger.info("Migrating: creating prediction_accuracy table")
                self.conn.execute("""
                    CREATE TABLE prediction_accuracy (
                        deployment TEXT PRIMARY KEY,
                        total_predictions INTEGER DEFAULT 0,
                        accurate_predictions INTEGER DEFAULT 0,
                        false_positives INTEGER DEFAULT 0,
                        false_negatives INTEGER DEFAULT 0,
                        avg_accuracy REAL DEFAULT 0.0,
                        last_updated DATETIME
                    )
                """)
            
            self.conn.commit()
            logger.debug("Schema migration completed")
        except Exception as e:
            logger.warning(f"Error during schema migration: {e}")
            # Don't fail on migration errors, just log them
    
    def _init_schema(self):
        """Initialize database schema"""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS metrics_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                deployment TEXT,
                namespace TEXT,
                node_utilization REAL,
                pod_count INTEGER,
                pod_cpu_usage REAL,
                hpa_target INTEGER,
                confidence REAL,
                scheduling_spike BOOLEAN,
                action_taken TEXT,
                cpu_request INTEGER,
                memory_request INTEGER,
                memory_usage REAL,
                node_selector TEXT
            );
            
            CREATE INDEX IF NOT EXISTS idx_metrics_deployment_time 
            ON metrics_history(deployment, timestamp);
            
            CREATE TABLE IF NOT EXISTS cost_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                deployment TEXT,
                avg_pod_count REAL,
                avg_utilization REAL,
                wasted_capacity_percent REAL,
                estimated_monthly_cost REAL,
                optimization_potential REAL,
                recommendation TEXT
            );
            
            CREATE TABLE IF NOT EXISTS anomalies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                deployment TEXT,
                anomaly_type TEXT,
                severity TEXT,
                description TEXT,
                current_value REAL,
                expected_value REAL,
                deviation_percent REAL
            );
            
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                deployment TEXT,
                predicted_cpu REAL,
                confidence REAL,
                recommended_action TEXT,
                reasoning TEXT,
                actual_cpu REAL,
                validated BOOLEAN DEFAULT 0,
                accuracy REAL
            );
            
            CREATE TABLE IF NOT EXISTS prediction_accuracy (
                deployment TEXT PRIMARY KEY,
                total_predictions INTEGER DEFAULT 0,
                accurate_predictions INTEGER DEFAULT 0,
                false_positives INTEGER DEFAULT 0,
                false_negatives INTEGER DEFAULT 0,
                avg_accuracy REAL DEFAULT 0.0,
                last_updated DATETIME
            );
            
            CREATE TABLE IF NOT EXISTS optimal_targets (
                deployment TEXT PRIMARY KEY,
                optimal_target INTEGER,
                confidence REAL,
                samples_count INTEGER,
                last_updated DATETIME
            );
            
            CREATE TABLE IF NOT EXISTS notification_providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                provider_type TEXT NOT NULL,
                webhook_url TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                alert_types TEXT DEFAULT 'all',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.conn.commit()
    
    def _cleanup_old_data(self, force: bool = False):
        """
        Clean up old data to prevent database growth.
        
        Args:
            force: If True, run cleanup regardless of interval
        """
        # Check if cleanup is needed (every cleanup_interval_hours)
        if not force:
            hours_since_cleanup = (datetime.now() - self._last_cleanup).total_seconds() / 3600
            if hours_since_cleanup < self.cleanup_interval_hours:
                return
        
        try:
            # Delete metrics older than retention period
            cursor = self.conn.execute("""
                DELETE FROM metrics_history 
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            """, (self.metrics_retention_days,))
            deleted_count = cursor.rowcount
            
            # Delete old anomalies
            cursor = self.conn.execute("""
                DELETE FROM anomalies 
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            """, (self.anomalies_retention_days,))
            deleted_anomalies = cursor.rowcount
            
            # Delete old predictions
            cursor = self.conn.execute("""
                DELETE FROM predictions 
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            """, (self.predictions_retention_days,))
            deleted_predictions = cursor.rowcount
            
            self.conn.commit()
            self._last_cleanup = datetime.now()
            
            if deleted_count > 0 or deleted_anomalies > 0 or deleted_predictions > 0:
                logger.info(
                    f"Database cleanup: deleted {deleted_count} metrics, "
                    f"{deleted_anomalies} anomalies, {deleted_predictions} predictions"
                )
            
            # Vacuum database periodically to reclaim space
            # Only do this if significant data was deleted
            if deleted_count > 1000 or deleted_anomalies > 100 or deleted_predictions > 100:
                logger.info("Running VACUUM to reclaim database space...")
                self.conn.execute("VACUUM")
                self.conn.commit()
                
            # Log database size
            self._log_database_stats()
                
        except Exception as e:
            logger.warning(f"Error during database cleanup: {e}")
    
    def _log_database_stats(self):
        """Log database statistics for monitoring"""
        try:
            # Get row counts
            metrics_count = self.conn.execute("SELECT COUNT(*) FROM metrics_history").fetchone()[0]
            predictions_count = self.conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
            anomalies_count = self.conn.execute("SELECT COUNT(*) FROM anomalies").fetchone()[0]
            
            # Get database file size
            import os
            db_size_mb = os.path.getsize(self.db_path) / (1024 * 1024) if os.path.exists(self.db_path) else 0
            
            logger.info(
                f"Database stats: {metrics_count} metrics, {predictions_count} predictions, "
                f"{anomalies_count} anomalies, size={db_size_mb:.1f}MB"
            )
        except Exception as e:
            logger.debug(f"Error getting database stats: {e}")
    
    def periodic_cleanup(self):
        """
        Run periodic cleanup. Call this from the main loop.
        Includes disk space check for auto-healing.
        """
        # First check disk space and heal if needed
        emergency_triggered = self._check_disk_and_heal()
        
        # If emergency cleanup was triggered, skip normal cleanup
        if not emergency_triggered:
            self._cleanup_old_data(force=False)
    
    def get_disk_status(self) -> dict:
        """
        Get current disk status for monitoring/dashboard.
        
        Returns:
            Dict with disk usage info and health status
        """
        disk = self._get_disk_usage()
        
        if disk['percent'] >= self.disk_emergency_threshold:
            status = 'emergency'
            message = 'Disk critically full - emergency cleanup active'
        elif disk['percent'] >= self.disk_critical_threshold:
            status = 'critical'
            message = 'Disk nearly full - aggressive cleanup active'
        elif disk['percent'] >= self.disk_warning_threshold:
            status = 'warning'
            message = 'Disk usage high - consider increasing PVC'
        else:
            status = 'healthy'
            message = 'Disk usage normal'
        
        return {
            'status': status,
            'message': message,
            'percent_used': round(disk['percent'] * 100, 1),
            'total_gb': round(disk['total_gb'], 2),
            'used_gb': round(disk['used_gb'], 2),
            'free_gb': round(disk['free_gb'], 2),
            'thresholds': {
                'warning': self.disk_warning_threshold * 100,
                'critical': self.disk_critical_threshold * 100,
                'emergency': self.disk_emergency_threshold * 100
            }
        }
    
    def close(self):
        """Close database connection properly"""
        if hasattr(self, 'conn') and self.conn:
            try:
                # Final cleanup before closing
                self._cleanup_old_data(force=True)
                self.conn.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database: {e}")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
    
    def store_metrics(self, snapshot: MetricsSnapshot):
        """Store metrics snapshot"""
        self.conn.execute("""
            INSERT INTO metrics_history 
            (timestamp, deployment, namespace, node_utilization, pod_count, 
             pod_cpu_usage, hpa_target, confidence, scheduling_spike, action_taken, 
             cpu_request, memory_request, memory_usage, node_selector)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot.timestamp, snapshot.deployment, snapshot.namespace,
            snapshot.node_utilization, snapshot.pod_count, snapshot.pod_cpu_usage,
            snapshot.hpa_target, snapshot.confidence, snapshot.scheduling_spike,
            snapshot.action_taken, snapshot.cpu_request, 
            snapshot.memory_request, snapshot.memory_usage, snapshot.node_selector
        ))
        self.conn.commit()
    
    def get_historical_pattern(self, deployment: str, hour: int, day_of_week: int, days_back: int = 30) -> List[float]:
        """Get historical CPU patterns for specific time"""
        cursor = self.conn.execute("""
            SELECT node_utilization 
            FROM metrics_history
            WHERE deployment = ?
            AND strftime('%H', timestamp) = ?
            AND strftime('%w', timestamp) = ?
            AND timestamp >= datetime('now', ? || ' days')
            ORDER BY timestamp DESC
        """, (deployment, f"{hour:02d}", str(day_of_week), f"-{days_back}"))
        
        return [row[0] for row in cursor.fetchall()]
    
    def get_recent_metrics(self, deployment: str, hours: int = 24) -> List[MetricsSnapshot]:
        """Get recent metrics for deployment"""
        cursor = self.conn.execute("""
            SELECT * FROM metrics_history
            WHERE deployment = ?
            AND timestamp >= datetime('now', ? || ' hours')
            ORDER BY timestamp DESC
        """, (deployment, f"-{hours}"))
        
        snapshots = []
        for row in cursor.fetchall():
            try:
                # Handle both string and datetime timestamp formats
                if isinstance(row[1], str):
                    timestamp = datetime.fromisoformat(row[1])
                else:
                    timestamp = row[1]
                
                # Handle old records without memory fields (default to 0)
                memory_request = row[12] if len(row) > 12 else 0
                memory_usage = row[13] if len(row) > 13 else 0.0
                node_selector = row[14] if len(row) > 14 else (row[12] if len(row) > 12 else "")
                
                snapshots.append(MetricsSnapshot(
                    timestamp=timestamp,
                    deployment=row[2],
                    namespace=row[3],
                    node_utilization=row[4],
                    pod_count=row[5],
                    pod_cpu_usage=row[6],
                    hpa_target=row[7],
                    confidence=row[8],
                    scheduling_spike=bool(row[9]),
                    action_taken=row[10],
                    cpu_request=row[11],
                    memory_request=memory_request,
                    memory_usage=memory_usage,
                    node_selector=node_selector
                ))
            except (ValueError, IndexError, TypeError) as e:
                logger.warning(f"Error parsing metrics row: {e}, skipping")
                continue
        
        return snapshots
    
    def get_observation_days(self, deployment: str) -> int:
        """
        Get the number of days of observation data for a deployment.
        Used by Autopilot to determine if enough data exists for recommendations.
        
        Args:
            deployment: Deployment name
            
        Returns:
            Number of days with data
        """
        try:
            cursor = self.conn.execute("""
                SELECT MIN(timestamp), MAX(timestamp)
                FROM metrics_history
                WHERE deployment = ?
            """, (deployment,))
            
            result = cursor.fetchone()
            if result and result[0] and result[1]:
                min_time = result[0]
                max_time = result[1]
                
                # Parse timestamps
                if isinstance(min_time, str):
                    min_time = datetime.fromisoformat(min_time)
                if isinstance(max_time, str):
                    max_time = datetime.fromisoformat(max_time)
                
                delta = max_time - min_time
                return max(1, delta.days)
            
            return 0
        except Exception as e:
            logger.warning(f"Error getting observation days for {deployment}: {e}")
            return 0
    
    def get_p95_metrics(self, deployment: str, hours: int = 168) -> Optional[Dict]:
        """
        Get P95 CPU and memory usage for a deployment.
        Used by Autopilot for resource recommendations.
        
        Args:
            deployment: Deployment name
            hours: Hours of data to analyze (default: 168 = 1 week)
            
        Returns:
            Dict with cpu_p95 (in cores), memory_p95 (in MB), or None if insufficient data
        """
        try:
            # Get metrics from the specified time period
            cursor = self.conn.execute("""
                SELECT pod_cpu_usage, memory_usage
                FROM metrics_history
                WHERE deployment = ?
                AND timestamp >= datetime('now', ? || ' hours')
                AND pod_cpu_usage IS NOT NULL
                ORDER BY timestamp DESC
            """, (deployment, f"-{hours}"))
            
            rows = cursor.fetchall()
            
            if len(rows) < 10:  # Need at least 10 data points
                return None
            
            cpu_values = [row[0] for row in rows if row[0] is not None and row[0] > 0]
            memory_values = [row[1] for row in rows if row[1] is not None and row[1] > 0]
            
            if len(cpu_values) < 10:
                return None
            
            # Calculate P95 (95th percentile)
            cpu_values.sort()
            memory_values.sort() if memory_values else []
            
            cpu_p95_idx = int(len(cpu_values) * 0.95)
            cpu_p95 = cpu_values[min(cpu_p95_idx, len(cpu_values) - 1)]
            
            memory_p95 = 0
            if memory_values:
                memory_p95_idx = int(len(memory_values) * 0.95)
                memory_p95 = memory_values[min(memory_p95_idx, len(memory_values) - 1)]
            
            return {
                'cpu_p95': cpu_p95,  # In cores
                'memory_p95': memory_p95,  # In MB
                'data_points': len(cpu_values),
                'hours_analyzed': hours
            }
            
        except Exception as e:
            logger.warning(f"Error getting P95 metrics for {deployment}: {e}")
            return None
    
    def store_anomaly(self, anomaly: AnomalyAlert):
        """Store anomaly"""
        self.conn.execute("""
            INSERT INTO anomalies 
            (timestamp, deployment, anomaly_type, severity, description, 
             current_value, expected_value, deviation_percent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            anomaly.timestamp, anomaly.deployment, anomaly.anomaly_type,
            anomaly.severity, anomaly.description, anomaly.current_value,
            anomaly.expected_value, anomaly.deviation_percent
        ))
        self.conn.commit()
    
    def store_prediction(self, prediction: Prediction):
        """Store prediction"""
        self.conn.execute("""
            INSERT INTO predictions 
            (timestamp, deployment, predicted_cpu, confidence, recommended_action, reasoning, validated)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (
            prediction.timestamp, prediction.deployment, prediction.predicted_cpu,
            prediction.confidence, prediction.recommended_action, prediction.reasoning
        ))
        self.conn.commit()
    
    def validate_predictions(self, deployment: str, hours_back: int = 2):
        """Validate predictions by comparing with actual CPU usage"""
        # Get predictions from last N hours that haven't been validated
        cursor = self.conn.execute("""
            SELECT id, timestamp, predicted_cpu, recommended_action
            FROM predictions
            WHERE deployment = ?
            AND validated = 0
            AND timestamp >= datetime('now', '-' || ? || ' hours')
            ORDER BY timestamp DESC
        """, (deployment, hours_back))
        
        predictions_to_validate = cursor.fetchall()
        
        for pred_id, pred_timestamp, predicted_cpu, action in predictions_to_validate:
            # Get actual CPU usage at the time prediction was for (1 hour after prediction)
            if isinstance(pred_timestamp, str):
                validation_time = datetime.fromisoformat(pred_timestamp)
            else:
                validation_time = pred_timestamp
            validation_time = validation_time + timedelta(hours=1)  # Check 1 hour after prediction
            
            # Get actual CPU usage around validation time (±15 minutes)
            cursor = self.conn.execute("""
                SELECT AVG(pod_cpu_usage), AVG(pod_count)
                FROM metrics_history
                WHERE deployment = ?
                AND timestamp >= datetime(?, '-15 minutes')
                AND timestamp <= datetime(?, '+15 minutes')
            """, (deployment, validation_time.isoformat(), validation_time.isoformat()))
            
            result = cursor.fetchone()
            if result and result[0] is not None:
                actual_avg_cpu = result[0]
                actual_pod_count = result[1] or 1
                
                # Calculate actual CPU utilization percentage
                # Need CPU request to calculate percentage
                cursor = self.conn.execute("""
                    SELECT AVG(cpu_request)
                    FROM metrics_history
                    WHERE deployment = ?
                    AND timestamp >= datetime(?, '-15 minutes')
                    AND timestamp <= datetime(?, '+15 minutes')
                """, (deployment, validation_time.isoformat(), validation_time.isoformat()))
                
                cpu_request_result = cursor.fetchone()
                if cpu_request_result and cpu_request_result[0]:
                    cpu_request_cores = (cpu_request_result[0] / 1000.0) * actual_pod_count
                    actual_cpu_percent = (actual_avg_cpu / cpu_request_cores * 100) if cpu_request_cores > 0 else 0
                    
                    # Calculate accuracy (how close was prediction)
                    error = abs(predicted_cpu - actual_cpu_percent)
                    accuracy = max(0.0, 1.0 - (error / 100.0))  # 100% if exact, 0% if 100% off
                    
                    # Mark as validated
                    self.conn.execute("""
                        UPDATE predictions
                        SET actual_cpu = ?, validated = 1, accuracy = ?
                        WHERE id = ?
                    """, (actual_cpu_percent, accuracy, pred_id))
                    
                    # Update accuracy tracking
                    self._update_prediction_accuracy(deployment, predicted_cpu, actual_cpu_percent, action)
        
        self.conn.commit()
    
    def _update_prediction_accuracy(self, deployment: str, predicted: float, actual: float, action: str):
        """Update prediction accuracy statistics"""
        # Get current stats
        cursor = self.conn.execute("""
            SELECT total_predictions, accurate_predictions, false_positives, false_negatives, avg_accuracy
            FROM prediction_accuracy
            WHERE deployment = ?
        """, (deployment,))
        
        result = cursor.fetchone()
        if result:
            total, accurate, fp, fn, avg_acc = result
        else:
            total, accurate, fp, fn, avg_acc = 0, 0, 0, 0, 0.0
        
        total += 1
        
        # Determine if prediction was accurate
        error = abs(predicted - actual)
        is_accurate = error < 15.0  # Within 15% is considered accurate
        
        if is_accurate:
            accurate += 1
        else:
            # Check for false positive/negative
            if action == "pre_scale_up" and actual < predicted - 20:
                # Predicted high but actual was low - false positive
                fp += 1
            elif action == "scale_down" and actual > predicted + 20:
                # Predicted low but actual was high - false negative
                fn += 1
        
        # Update average accuracy
        accuracy_value = max(0.0, 1.0 - (error / 100.0))
        if avg_acc == 0:
            new_avg = accuracy_value
        else:
            new_avg = (avg_acc * (total - 1) + accuracy_value) / total
        
        # Store updated stats
        self.conn.execute("""
            INSERT OR REPLACE INTO prediction_accuracy
            (deployment, total_predictions, accurate_predictions, false_positives, 
             false_negatives, avg_accuracy, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (deployment, total, accurate, fp, fn, new_avg, datetime.now()))
    
    def get_prediction_accuracy(self, deployment: str) -> Optional[Dict]:
        """Get prediction accuracy statistics"""
        cursor = self.conn.execute("""
            SELECT total_predictions, accurate_predictions, false_positives, 
                   false_negatives, avg_accuracy
            FROM prediction_accuracy
            WHERE deployment = ?
        """, (deployment,))
        
        result = cursor.fetchone()
        if result and result[0] and result[0] > 0:
            total, accurate, fp, fn, avg_acc = result
            accuracy_rate = (accurate / total * 100) if total > 0 else 0
            false_positive_rate = (fp / total * 100) if total > 0 else 0
            
            return {
                'total_predictions': total,
                'accurate_predictions': accurate,
                'accuracy_rate': accuracy_rate,
                'false_positives': fp,
                'false_positive_rate': false_positive_rate,
                'false_negatives': fn,
                'avg_accuracy': avg_acc
            }
        return None
    
    def get_optimal_target(self, deployment: str) -> Optional[int]:
        """Get learned optimal target"""
        cursor = self.conn.execute("""
            SELECT optimal_target, confidence 
            FROM optimal_targets
            WHERE deployment = ?
        """, (deployment,))
        
        row = cursor.fetchone()
        return row[0] if row and row[1] > 0.7 else None
    
    def update_optimal_target(self, deployment: str, target: int, confidence: float):
        """Update optimal target with proper error handling and verification"""
        try:
            # First, check if record exists
            cursor = self.conn.execute("""
                SELECT optimal_target, confidence, samples_count 
                FROM optimal_targets
                WHERE deployment = ?
            """, (deployment,))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing record
                new_samples = existing[2] + 1
                self.conn.execute("""
                    UPDATE optimal_targets
                    SET optimal_target = ?, confidence = ?, samples_count = ?, last_updated = ?
                    WHERE deployment = ?
                """, (target, confidence, new_samples, datetime.now(), deployment))
                logger.info(f"{deployment} - Updated optimal target: {target}% (confidence: {confidence:.0%}, samples: {new_samples})")
            else:
                # Insert new record
                self.conn.execute("""
                    INSERT INTO optimal_targets
                    (deployment, optimal_target, confidence, samples_count, last_updated)
                    VALUES (?, ?, ?, 1, ?)
                """, (deployment, target, confidence, datetime.now()))
                logger.info(f"{deployment} - Saved new optimal target: {target}% (confidence: {confidence:.0%})")
            
            self.conn.commit()
            
            # Verify the save
            cursor = self.conn.execute("""
                SELECT optimal_target, confidence, samples_count 
                FROM optimal_targets
                WHERE deployment = ?
            """, (deployment,))
            
            verified = cursor.fetchone()
            if verified:
                logger.debug(f"{deployment} - Verified optimal target in DB: {verified[0]}% (confidence: {verified[1]:.0%}, samples: {verified[2]})")
            else:
                logger.error(f"{deployment} - Failed to verify optimal target save!")
                
        except Exception as e:
            logger.error(f"{deployment} - Error updating optimal target: {e}", exc_info=True)
            self.conn.rollback()
    
    # Notification Provider Methods
    def get_notification_providers(self) -> List[Dict]:
        """Get all notification providers"""
        cursor = self.conn.execute("""
            SELECT id, name, provider_type, webhook_url, enabled, alert_types, created_at, updated_at
            FROM notification_providers
            ORDER BY name
        """)
        
        providers = []
        for row in cursor.fetchall():
            alert_types = row[5] if row[5] else 'all'
            providers.append({
                'id': row[0],
                'name': row[1],
                'provider_type': row[2],
                'webhook_url': row[3][:30] + '...' if len(row[3]) > 30 else row[3],
                'webhook_url_full': row[3],  # Full URL for internal use
                'enabled': bool(row[4]),
                'alert_types': alert_types.split(',') if alert_types != 'all' else ['all'],
                'created_at': row[6],
                'updated_at': row[7]
            })
        return providers
    
    def add_notification_provider(self, name: str, provider_type: str, webhook_url: str, 
                                    enabled: bool = True, alert_types: List[str] = None) -> Dict:
        """Add a new notification provider"""
        try:
            alert_types_str = ','.join(alert_types) if alert_types else 'all'
            self.conn.execute("""
                INSERT INTO notification_providers (name, provider_type, webhook_url, enabled, alert_types)
                VALUES (?, ?, ?, ?, ?)
            """, (name, provider_type, webhook_url, 1 if enabled else 0, alert_types_str))
            self.conn.commit()
            
            return {'success': True, 'message': f'Provider {name} added successfully'}
        except Exception as e:
            if 'UNIQUE constraint' in str(e):
                return {'success': False, 'error': f'Provider with name "{name}" already exists'}
            return {'success': False, 'error': str(e)}
    
    def update_notification_provider(self, provider_id: int, name: str = None, provider_type: str = None, 
                                     webhook_url: str = None, enabled: bool = None, 
                                     alert_types: List[str] = None) -> Dict:
        """Update an existing notification provider"""
        try:
            updates = []
            params = []
            
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if provider_type is not None:
                updates.append("provider_type = ?")
                params.append(provider_type)
            if webhook_url is not None:
                updates.append("webhook_url = ?")
                params.append(webhook_url)
            if enabled is not None:
                updates.append("enabled = ?")
                params.append(1 if enabled else 0)
            if alert_types is not None:
                updates.append("alert_types = ?")
                params.append(','.join(alert_types) if alert_types else 'all')
            
            if not updates:
                return {'success': False, 'error': 'No fields to update'}
            
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(provider_id)
            
            self.conn.execute(f"""
                UPDATE notification_providers
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)
            self.conn.commit()
            
            return {'success': True, 'message': 'Provider updated successfully'}
        except Exception as e:
            if 'UNIQUE constraint' in str(e):
                return {'success': False, 'error': f'Provider with name "{name}" already exists'}
            return {'success': False, 'error': str(e)}
    
    def delete_notification_provider(self, provider_id: int) -> Dict:
        """Delete a notification provider"""
        try:
            cursor = self.conn.execute("""
                DELETE FROM notification_providers WHERE id = ?
            """, (provider_id,))
            self.conn.commit()
            
            if cursor.rowcount > 0:
                return {'success': True, 'message': 'Provider deleted successfully'}
            return {'success': False, 'error': 'Provider not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_notification_provider(self, provider_id: int) -> Dict:
        """Test a notification provider by sending a test message"""
        cursor = self.conn.execute("""
            SELECT name, provider_type, webhook_url
            FROM notification_providers
            WHERE id = ?
        """, (provider_id,))
        
        row = cursor.fetchone()
        if not row:
            return {'success': False, 'error': 'Provider not found'}
        
        name, provider_type, webhook_url = row
        return {'name': name, 'provider_type': provider_type, 'webhook_url': webhook_url}


class AlertManager:
    """Manage alerts to various channels"""
    
    def __init__(self, webhooks: Optional[Dict[str, str]] = None):
        self.webhooks = webhooks or {}
    
    def send_alert(self, title: str, message: str, severity: str = "info", fields: Dict = None):
        """Send alert to all channels"""
        for channel, webhook_url in self.webhooks.items():
            try:
                if channel == "slack":
                    self._send_slack(webhook_url, title, message, severity, fields)
                elif channel == "teams":
                    self._send_teams(webhook_url, title, message, severity, fields)
                elif channel == "discord":
                    self._send_discord(webhook_url, title, message, severity, fields)
                elif channel == "generic":
                    self._send_generic(webhook_url, title, message, severity, fields)
            except Exception as e:
                logger.error(f"Failed to send alert to {channel}: {e}")
    
    def _send_slack(self, webhook_url: str, title: str, message: str, severity: str, fields: Dict):
        """Send to Slack"""
        color = {"info": "#36a64f", "warning": "#ff9900", "critical": "#ff0000"}.get(severity, "#36a64f")
        
        payload = {
            "attachments": [{
                "color": color,
                "title": f"{self._get_emoji(severity)} {title}",
                "text": message,
                "fields": [{"title": k, "value": str(v), "short": True} for k, v in (fields or {}).items()],
                "footer": "Smart Autoscaler",
                "ts": int(datetime.now().timestamp())
            }]
        }
        
        requests.post(webhook_url, json=payload, timeout=5)
    
    def _send_teams(self, webhook_url: str, title: str, message: str, severity: str, fields: Dict):
        """Send to Teams"""
        color = {"info": "00FF00", "warning": "FFA500", "critical": "FF0000"}.get(severity, "00FF00")
        
        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "themeColor": color,
            "title": f"{self._get_emoji(severity)} {title}",
            "text": message,
            "sections": [{
                "facts": [{"name": k, "value": str(v)} for k, v in (fields or {}).items()]
            }]
        }
        
        requests.post(webhook_url, json=payload, timeout=5)
    
    def _send_discord(self, webhook_url: str, title: str, message: str, severity: str, fields: Dict):
        """Send to Discord"""
        color = {"info": 3066993, "warning": 16763904, "critical": 16711680}.get(severity, 3066993)
        
        payload = {
            "embeds": [{
                "title": f"{self._get_emoji(severity)} {title}",
                "description": message,
                "color": color,
                "fields": [{"name": k, "value": str(v), "inline": True} for k, v in (fields or {}).items()],
                "footer": {"text": "Smart Autoscaler"},
                "timestamp": datetime.utcnow().isoformat()
            }]
        }
        
        requests.post(webhook_url, json=payload, timeout=5)
    
    def _send_generic(self, webhook_url: str, title: str, message: str, severity: str, fields: Dict):
        """Send to generic webhook"""
        payload = {
            "title": title,
            "message": message,
            "severity": severity,
            "fields": fields or {},
            "timestamp": datetime.now().isoformat()
        }
        
        requests.post(webhook_url, json=payload, timeout=5)
    
    def _get_emoji(self, severity: str) -> str:
        return {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(severity, "ℹ️")


class PatternRecognizer:
    """
    Learn patterns from historical data with multiple prediction windows.
    
    Features:
    - Multiple prediction windows (15min, 30min, 1hr, 2hr)
    - Model selection based on workload type
    - Ensemble predictions combining multiple models
    - Weekly and monthly pattern recognition
    """
    
    def __init__(self, db: TimeSeriesDatabase):
        self.db = db
        
        # Prediction windows in minutes
        self.prediction_windows = {
            '15min': 15,
            '30min': 30,
            '1hr': 60,
            '2hr': 120
        }
        
        # Model weights per workload type
        self.model_weights = {
            'steady': {'mean': 0.6, 'trend': 0.2, 'seasonal': 0.2},
            'bursty': {'mean': 0.3, 'trend': 0.1, 'recent': 0.6},
            'periodic': {'mean': 0.2, 'trend': 0.2, 'seasonal': 0.6},
            'growing': {'mean': 0.2, 'trend': 0.6, 'seasonal': 0.2},
            'declining': {'mean': 0.2, 'trend': 0.6, 'seasonal': 0.2},
            'unknown': {'mean': 0.5, 'trend': 0.25, 'seasonal': 0.25}
        }
        
        # Cache for workload types
        self._workload_type_cache: Dict[str, Tuple[str, datetime]] = {}
    
    def learn_daily_pattern(self, deployment: str) -> Dict[int, float]:
        """Learn average CPU by hour"""
        pattern = {}
        for hour in range(24):
            values = []
            for day in range(7):
                historical = self.db.get_historical_pattern(deployment, hour, day, days_back=30)
                values.extend(historical)
            
            if values:
                pattern[hour] = statistics.mean(values)
        
        return pattern
    
    def learn_weekly_pattern(self, deployment: str) -> Dict[int, Dict[int, float]]:
        """
        Learn weekly patterns (different patterns for each day of week).
        
        Returns:
            Dict mapping day_of_week -> hour -> avg_cpu
        """
        pattern = {}
        for day in range(7):  # 0=Monday, 6=Sunday
            pattern[day] = {}
            for hour in range(24):
                historical = self.db.get_historical_pattern(deployment, hour, day, days_back=30)
                if historical:
                    pattern[day][hour] = statistics.mean(historical)
        return pattern
    
    def detect_workload_type(self, deployment: str) -> str:
        """
        Detect workload type for model selection.
        
        Returns:
            One of: 'steady', 'bursty', 'periodic', 'growing', 'declining', 'unknown'
        """
        # Check cache (valid for 1 hour)
        if deployment in self._workload_type_cache:
            cached_type, cached_time = self._workload_type_cache[deployment]
            if (datetime.now() - cached_time).total_seconds() < 3600:
                return cached_type
        
        recent = self.db.get_recent_metrics(deployment, hours=24)
        if len(recent) < 20:
            return 'unknown'
        
        cpu_values = [m.pod_cpu_usage for m in recent if m.pod_cpu_usage > 0]
        if len(cpu_values) < 10:
            return 'unknown'
        
        mean = statistics.mean(cpu_values)
        std = statistics.stdev(cpu_values) if len(cpu_values) > 1 else 0
        cv = std / mean if mean > 0 else 0
        
        # Classify based on coefficient of variation
        if cv < 0.15:
            workload_type = 'steady'
        elif cv > 0.5:
            workload_type = 'bursty'
        else:
            # Check for trend
            if len(cpu_values) >= 50:
                first_half = statistics.mean(cpu_values[:len(cpu_values)//2])
                second_half = statistics.mean(cpu_values[len(cpu_values)//2:])
                change = (second_half - first_half) / first_half if first_half > 0 else 0
                
                if change > 0.2:
                    workload_type = 'growing'
                elif change < -0.2:
                    workload_type = 'declining'
                else:
                    workload_type = 'periodic'
            else:
                workload_type = 'periodic'
        
        # Cache result
        self._workload_type_cache[deployment] = (workload_type, datetime.now())
        logger.debug(f"{deployment} - Detected workload type: {workload_type} (cv={cv:.2f})")
        
        return workload_type
    
    def predict_multi_window(self, deployment: str) -> Dict[str, Tuple[float, float]]:
        """
        Predict CPU for multiple time windows.
        
        Returns:
            Dict mapping window_name -> (predicted_cpu, confidence)
        """
        predictions = {}
        workload_type = self.detect_workload_type(deployment)
        
        for window_name, minutes in self.prediction_windows.items():
            predicted, confidence = self._predict_for_window(deployment, minutes, workload_type)
            predictions[window_name] = (predicted, confidence)
        
        return predictions
    
    def _predict_for_window(self, deployment: str, minutes_ahead: int, workload_type: str) -> Tuple[float, float]:
        """
        Predict CPU for a specific time window using ensemble models.
        
        Args:
            deployment: Deployment name
            minutes_ahead: Minutes to predict ahead
            workload_type: Type of workload for model selection
        
        Returns:
            Tuple of (predicted_cpu, confidence)
        """
        now = datetime.now()
        target_time = now + timedelta(minutes=minutes_ahead)
        target_hour = target_time.hour
        target_day = target_time.weekday()
        
        # Get model weights for this workload type
        weights = self.model_weights.get(workload_type, self.model_weights['unknown'])
        
        predictions = []
        confidences = []
        
        # Model 1: Historical mean for this hour/day
        historical = self.db.get_historical_pattern(deployment, target_hour, target_day, days_back=30)
        if len(historical) >= 3:
            mean_pred = statistics.mean(historical)
            stddev = statistics.stdev(historical) if len(historical) > 1 else 0
            mean_conf = max(0.3, min(0.95, 1 - (stddev / (mean_pred + 0.001))))
            predictions.append(('mean', mean_pred, mean_conf, weights['mean']))
        
        # Model 2: Trend-based prediction
        recent = self.db.get_recent_metrics(deployment, hours=4)
        if len(recent) >= 10:
            cpu_values = [m.pod_cpu_usage for m in recent if m.pod_cpu_usage > 0]
            if len(cpu_values) >= 5:
                # Simple linear trend
                n = len(cpu_values)
                x_mean = (n - 1) / 2
                y_mean = statistics.mean(cpu_values)
                
                numerator = sum((i - x_mean) * (cpu_values[i] - y_mean) for i in range(n))
                denominator = sum((i - x_mean) ** 2 for i in range(n))
                
                if denominator > 0:
                    slope = numerator / denominator
                    # Project forward (assuming 1 data point per minute)
                    trend_pred = y_mean + slope * (n + minutes_ahead)
                    trend_pred = max(0, min(100, trend_pred))  # Clamp to valid range
                    
                    # Confidence based on R-squared
                    ss_res = sum((cpu_values[i] - (y_mean + slope * (i - x_mean))) ** 2 for i in range(n))
                    ss_tot = sum((cpu_values[i] - y_mean) ** 2 for i in range(n))
                    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
                    trend_conf = max(0.3, min(0.9, r_squared))
                    
                    predictions.append(('trend', trend_pred, trend_conf, weights['trend']))
        
        # Model 3: Seasonal/periodic prediction (weekly pattern)
        weekly_pattern = self.learn_weekly_pattern(deployment)
        if target_day in weekly_pattern and target_hour in weekly_pattern[target_day]:
            seasonal_pred = weekly_pattern[target_day][target_hour]
            # Higher confidence if we have consistent weekly patterns
            all_day_values = list(weekly_pattern[target_day].values())
            if all_day_values:
                seasonal_conf = 0.7 if len(all_day_values) >= 12 else 0.5
                predictions.append(('seasonal', seasonal_pred, seasonal_conf, weights['seasonal']))
        
        # Model 4: Recent average (for bursty workloads)
        if 'recent' in weights and weights['recent'] > 0:
            recent_short = self.db.get_recent_metrics(deployment, hours=1)
            if len(recent_short) >= 3:
                recent_cpu = [m.pod_cpu_usage for m in recent_short if m.pod_cpu_usage > 0]
                if recent_cpu:
                    recent_pred = statistics.mean(recent_cpu)
                    recent_conf = 0.6  # Lower confidence for short-term
                    predictions.append(('recent', recent_pred, recent_conf, weights['recent']))
        
        if not predictions:
            return 0.0, 0.0
        
        # Ensemble: weighted average
        total_weight = sum(p[3] * p[2] for p in predictions)  # weight * confidence
        if total_weight == 0:
            return 0.0, 0.0
        
        ensemble_pred = sum(p[1] * p[3] * p[2] for p in predictions) / total_weight
        ensemble_conf = sum(p[2] * p[3] for p in predictions) / sum(p[3] for p in predictions)
        
        # Reduce confidence for longer prediction windows
        window_penalty = 1.0 - (minutes_ahead / 240)  # Max 2hr = 120min, penalty up to 50%
        ensemble_conf *= max(0.5, window_penalty)
        
        logger.debug(
            f"{deployment} - Prediction for +{minutes_ahead}min: {ensemble_pred:.1f}% "
            f"(confidence: {ensemble_conf:.0%}, models: {[p[0] for p in predictions]})"
        )
        
        return ensemble_pred, ensemble_conf
    
    def predict_next_hour(self, deployment: str) -> Tuple[float, float]:
        """Predict CPU for next hour (backward compatible)"""
        workload_type = self.detect_workload_type(deployment)
        return self._predict_for_window(deployment, 60, workload_type)
    
    def get_best_prediction_window(self, deployment: str) -> Tuple[str, float, float]:
        """
        Get the best prediction window based on confidence.
        
        Returns:
            Tuple of (window_name, predicted_cpu, confidence)
        """
        predictions = self.predict_multi_window(deployment)
        
        if not predictions:
            return '1hr', 0.0, 0.0
        
        # Find window with highest confidence
        best_window = max(predictions.items(), key=lambda x: x[1][1])
        return best_window[0], best_window[1][0], best_window[1][1]


class AnomalyDetector:
    """Detect anomalies in metrics"""
    
    def __init__(self, db: TimeSeriesDatabase, alert_manager: AlertManager):
        self.db = db
        self.alert_manager = alert_manager
    
    def detect_anomalies(self, deployment: str, current_snapshot: MetricsSnapshot) -> List[AnomalyAlert]:
        """Detect anomalies"""
        anomalies = []
        recent = self.db.get_recent_metrics(deployment, hours=24)
        
        if len(recent) < 10:
            return anomalies
        
        # CPU spike anomaly
        recent_cpu = [s.node_utilization for s in recent[-20:]]
        avg_cpu = statistics.mean(recent_cpu)
        stddev_cpu = statistics.stdev(recent_cpu) if len(recent_cpu) > 1 else 0
        
        if current_snapshot.node_utilization > avg_cpu + (3 * stddev_cpu):
            deviation = ((current_snapshot.node_utilization - avg_cpu) / avg_cpu * 100)
            anomaly = AnomalyAlert(
                timestamp=datetime.now(),
                deployment=deployment,
                anomaly_type="cpu_spike",
                severity="warning" if deviation < 50 else "critical",
                description=f"Unusual CPU spike detected",
                current_value=current_snapshot.node_utilization,
                expected_value=avg_cpu,
                deviation_percent=deviation
            )
            anomalies.append(anomaly)
            self.db.store_anomaly(anomaly)
            
            self.alert_manager.send_alert(
                title=f"CPU Anomaly: {deployment}",
                message=f"CPU spiked to {current_snapshot.node_utilization:.1f}% (expected {avg_cpu:.1f}%)",
                severity=anomaly.severity,
                fields={
                    "Deployment": deployment,
                    "Current CPU": f"{current_snapshot.node_utilization:.1f}%",
                    "Expected CPU": f"{avg_cpu:.1f}%",
                    "Deviation": f"+{deviation:.1f}%"
                }
            )
        
        # Scaling thrashing
        recent_actions = [s.action_taken for s in recent[-30:]]
        adjust_count = sum(1 for a in recent_actions if a in ['increase', 'decrease'])
        
        if adjust_count > 15:
            anomaly = AnomalyAlert(
                timestamp=datetime.now(),
                deployment=deployment,
                anomaly_type="scaling_thrashing",
                severity="warning",
                description=f"Excessive scaling activity ({adjust_count} adjustments)",
                current_value=adjust_count,
                expected_value=5.0,
                deviation_percent=(adjust_count - 5) / 5 * 100
            )
            anomalies.append(anomaly)
            self.db.store_anomaly(anomaly)
            
            self.alert_manager.send_alert(
                title=f"Scaling Thrashing: {deployment}",
                message=f"Detected {adjust_count} adjustments in 30 minutes",
                severity="warning",
                fields={"Deployment": deployment, "Adjustments": str(adjust_count)}
            )
        
        # Low efficiency alert (wasting resources)
        if len(recent) >= 50:
            avg_cpu_usage = statistics.mean([s.pod_cpu_usage * 100 for s in recent[-50:]])
            avg_cpu_request = statistics.mean([s.cpu_request for s in recent[-50:]])
            if avg_cpu_request > 0:
                efficiency = (avg_cpu_usage / (avg_cpu_request / 1000 * 100)) * 100
                if efficiency < 20:  # Less than 20% efficiency
                    anomaly = AnomalyAlert(
                        timestamp=datetime.now(),
                        deployment=deployment,
                        anomaly_type="low_efficiency",
                        severity="info",
                        description=f"Resource efficiency is very low ({efficiency:.0f}%). Consider reducing CPU request.",
                        current_value=efficiency,
                        expected_value=50.0,
                        deviation_percent=(50 - efficiency) / 50 * 100
                    )
                    anomalies.append(anomaly)
                    self.db.store_anomaly(anomaly)
        
        # High memory utilization alert
        if current_snapshot.memory_usage > 0 and current_snapshot.memory_request > 0:
            memory_util = (current_snapshot.memory_usage / current_snapshot.memory_request) * 100
            if memory_util > 90:
                anomaly = AnomalyAlert(
                    timestamp=datetime.now(),
                    deployment=deployment,
                    anomaly_type="high_memory",
                    severity="critical" if memory_util > 95 else "warning",
                    description=f"Memory utilization is very high ({memory_util:.0f}%). Risk of OOM.",
                    current_value=memory_util,
                    expected_value=70.0,
                    deviation_percent=(memory_util - 70) / 70 * 100
                )
                anomalies.append(anomaly)
                self.db.store_anomaly(anomaly)
                
                self.alert_manager.send_alert(
                    title=f"High Memory: {deployment}",
                    message=f"Memory at {memory_util:.0f}% - OOM risk!",
                    severity=anomaly.severity,
                    fields={
                        "Deployment": deployment,
                        "Memory Usage": f"{current_snapshot.memory_usage:.0f}MB",
                        "Memory Request": f"{current_snapshot.memory_request:.0f}MB"
                    }
                )
        
        # Low confidence predictions alert
        if current_snapshot.confidence < 0.5:
            anomaly = AnomalyAlert(
                timestamp=datetime.now(),
                deployment=deployment,
                anomaly_type="low_confidence",
                severity="info",
                description=f"Prediction confidence is low ({current_snapshot.confidence:.0%}). Scaling decisions may be unreliable.",
                current_value=current_snapshot.confidence * 100,
                expected_value=80.0,
                deviation_percent=(80 - current_snapshot.confidence * 100) / 80 * 100
            )
            anomalies.append(anomaly)
            self.db.store_anomaly(anomaly)
        
        return anomalies


class CostOptimizer:
    """Analyze and optimize costs"""
    
    def __init__(self, db: TimeSeriesDatabase, alert_manager: AlertManager):
        self.db = db
        self.alert_manager = alert_manager
        
        # Validate cost per vCPU
        import os
        cost_str = os.getenv('COST_PER_VCPU_HOUR', '0.04')
        try:
            from src.config_validator import ConfigValidator
            self.cost_per_vcpu_hour = ConfigValidator.validate_cost_per_vcpu(cost_str)
        except (ImportError, ValueError) as e:
            # Fallback if validator not available or invalid value
            try:
                val = float(cost_str)
                if val < 0 or val > 100:
                    raise ValueError(f"Cost out of range: {val}")
                self.cost_per_vcpu_hour = val
            except (ValueError, TypeError):
                logger.warning(f"Invalid COST_PER_VCPU_HOUR: {cost_str}, using default 0.04. Error: {e}")
                self.cost_per_vcpu_hour = 0.04
        
        # Cost per GB memory per hour (default: $0.004/GB-hour, typical cloud pricing)
        memory_cost_str = os.getenv('COST_PER_GB_MEMORY_HOUR', '0.004')
        try:
            self.cost_per_gb_memory_hour = float(memory_cost_str)
        except (ValueError, TypeError):
            logger.warning(f"Invalid COST_PER_GB_MEMORY_HOUR: {memory_cost_str}, using default 0.004")
            self.cost_per_gb_memory_hour = 0.004
    
    def calculate_resource_recommendations(self, deployment: str, hours: int = 168) -> Optional[Dict]:
        """
        Calculate optimized resource requests with adjusted HPA targets.
        
        This is critical for FinOps: When you reduce CPU/memory requests,
        you MUST adjust HPA targets to maintain the same scaling behavior.
        
        IMPORTANT: Minimum CPU request handling
        - Very low CPU requests (<100m) cause HPA scaling instability
        - When CPU request is too low, small usage changes cause large % swings
        - We enforce a minimum of 100m CPU request for stable HPA behavior
        
        Example:
        - Current: 1000m CPU request, 70% HPA target → scales at 700m usage
        - Optimized: 600m CPU request, 117% HPA target → scales at 700m usage (same!)
        
        Args:
            deployment: Deployment name
            hours: Hours of historical data to analyze (default: 1 week)
        
        Returns:
            Dict with recommendations including adjusted HPA targets
        """
        recent = self.db.get_recent_metrics(deployment, hours=hours)
        
        if len(recent) < 100:  # Need at least 100 data points for reliable recommendations
            return None
        
        # Calculate current resource usage statistics
        cpu_requests = [s.cpu_request for s in recent]  # millicores
        cpu_usages_raw = [s.pod_cpu_usage * 1000 for s in recent]  # Convert cores to millicores
        cpu_usages = [u for u in cpu_usages_raw if u > 0]  # Filter zeros for statistics
        memory_requests = [s.memory_request for s in recent if s.memory_request > 0]  # MB
        memory_usages = [s.memory_usage for s in recent if s.memory_usage > 0]  # MB
        hpa_targets = [s.hpa_target for s in recent if s.hpa_target > 0]
        
        if not cpu_requests:
            return None
        
        # If no valid CPU usage data, use raw values (may be all zeros)
        if not cpu_usages:
            cpu_usages = cpu_usages_raw if cpu_usages_raw else [0]
            return None
        
        # Current averages
        current_cpu_request = statistics.mean(cpu_requests)
        current_memory_request = statistics.mean(memory_requests) if memory_requests else 512
        current_hpa_target = statistics.mean(hpa_targets) if hpa_targets else 70
        
        # Usage statistics (use P95 for safety)
        avg_cpu_usage = statistics.mean(cpu_usages)
        p50_cpu_usage = statistics.median(cpu_usages)
        p95_cpu_usage = sorted(cpu_usages)[int(len(cpu_usages) * 0.95)]
        p99_cpu_usage = sorted(cpu_usages)[int(len(cpu_usages) * 0.99)]
        max_cpu_usage = max(cpu_usages)
        
        avg_memory_usage = statistics.mean(memory_usages) if memory_usages else 0
        p95_memory_usage = sorted(memory_usages)[int(len(memory_usages) * 0.95)] if memory_usages else 0
        max_memory_usage = max(memory_usages) if memory_usages else 0
        
        # Calculate current utilization
        current_cpu_utilization = (avg_cpu_usage / current_cpu_request * 100) if current_cpu_request > 0 else 0
        current_memory_utilization = (avg_memory_usage / current_memory_request * 100) if current_memory_request > 0 else 0
        
        # Calculate current scaling threshold (absolute value in millicores)
        current_scaling_threshold = current_cpu_request * (current_hpa_target / 100)
        
        # Smart CPU recommendation: Base buffer + percentage buffer
        # Formula: P95 + BASE_BUFFER + (P95 × PERCENT_BUFFER)
        # This ensures small workloads get meaningful buffers, large workloads don't over-provision
        CPU_BASE_BUFFER = 25  # 25m minimum buffer for any workload
        CPU_PERCENT_BUFFER = 0.20  # 20% additional buffer
        
        recommended_cpu_request = int(p95_cpu_usage + CPU_BASE_BUFFER + (p95_cpu_usage * CPU_PERCENT_BUFFER))
        
        # CRITICAL: Enforce minimum CPU request for HPA stability
        # Very low CPU requests cause scaling instability because:
        # 1. Small absolute changes in CPU usage cause large percentage swings
        # 2. HPA may thrash between min/max replicas
        # 3. Metrics collection granularity becomes significant
        MIN_CPU_REQUEST = 100  # 100m minimum for stable HPA
        
        if recommended_cpu_request < MIN_CPU_REQUEST:
            logger.info(
                f"{deployment} - Recommended CPU {recommended_cpu_request}m is below minimum {MIN_CPU_REQUEST}m. "
                f"Enforcing minimum for HPA stability."
            )
            recommended_cpu_request = MIN_CPU_REQUEST
        
        # Smart memory recommendation: Base buffer + percentage buffer
        # Formula: P95 + BASE_BUFFER + (P95 × PERCENT_BUFFER)
        # Memory is risky - OOM kills are worse than over-provisioning
        MEM_BASE_BUFFER = 64  # 64Mi minimum buffer for any workload
        MEM_PERCENT_BUFFER = 0.25  # 25% additional buffer (more conservative than CPU)
        
        if memory_usages:
            recommended_memory_request = int(p95_memory_usage + MEM_BASE_BUFFER + (p95_memory_usage * MEM_PERCENT_BUFFER))
        else:
            recommended_memory_request = int(current_memory_request)
        
        # Higher minimum for memory (256Mi) to avoid OOM risk
        MIN_MEMORY_REQUEST = 256  # 256Mi minimum for safety
        recommended_memory_request = max(MIN_MEMORY_REQUEST, recommended_memory_request)
        
        # Don't recommend memory reduction if it's less than 20% savings
        # Memory is too risky to optimize aggressively
        memory_reduction_percent = (1 - recommended_memory_request / current_memory_request) * 100 if current_memory_request > 0 else 0
        if memory_reduction_percent > 0 and memory_reduction_percent < 20:
            # Keep current memory if savings are small - not worth the OOM risk
            recommended_memory_request = int(current_memory_request)
        
        # CRITICAL: Calculate adjusted HPA target to maintain same scaling behavior
        # Formula: new_target = (old_threshold / new_request) * 100
        # This ensures the absolute CPU usage that triggers scaling remains the same
        adjusted_hpa_target = (current_scaling_threshold / recommended_cpu_request * 100) if recommended_cpu_request > 0 else current_hpa_target
        
        # Clamp HPA target to reasonable range (50-200%)
        # Note: HPA targets >100% are valid and mean "scale when usage exceeds request"
        adjusted_hpa_target = max(50, min(200, adjusted_hpa_target))
        
        # Special handling for low CPU requests: use higher HPA targets
        # This prevents false positive scaling from small CPU fluctuations
        if recommended_cpu_request <= 150:
            # For very low requests, use 85-90% target to avoid thrashing
            min_safe_target = 85
            if adjusted_hpa_target < min_safe_target:
                logger.info(
                    f"{deployment} - Low CPU request ({recommended_cpu_request}m), "
                    f"adjusting HPA target from {adjusted_hpa_target:.0f}% to {min_safe_target}% for stability"
                )
                adjusted_hpa_target = min_safe_target
        
        # Calculate cost savings
        avg_pod_count = statistics.mean([s.pod_count for s in recent])
        hours_per_month = 730
        
        # Current monthly cost
        current_cpu_cores = (current_cpu_request / 1000) * avg_pod_count
        current_memory_gb = (current_memory_request / 1024) * avg_pod_count
        current_monthly_cpu_cost = current_cpu_cores * self.cost_per_vcpu_hour * hours_per_month
        current_monthly_memory_cost = current_memory_gb * self.cost_per_gb_memory_hour * hours_per_month
        current_monthly_cost = current_monthly_cpu_cost + current_monthly_memory_cost
        
        # Optimized monthly cost
        optimized_cpu_cores = (recommended_cpu_request / 1000) * avg_pod_count
        optimized_memory_gb = (recommended_memory_request / 1024) * avg_pod_count
        optimized_monthly_cpu_cost = optimized_cpu_cores * self.cost_per_vcpu_hour * hours_per_month
        optimized_monthly_memory_cost = optimized_memory_gb * self.cost_per_gb_memory_hour * hours_per_month
        optimized_monthly_cost = optimized_monthly_cpu_cost + optimized_monthly_memory_cost
        
        # Savings
        monthly_savings = current_monthly_cost - optimized_monthly_cost
        savings_percent = (monthly_savings / current_monthly_cost * 100) if current_monthly_cost > 0 else 0
        
        # Determine recommendation level
        if savings_percent > 30:
            recommendation_level = "high"
            recommendation_text = "High optimization potential! Significant cost savings available."
        elif savings_percent > 15:
            recommendation_level = "medium"
            recommendation_text = "Moderate optimization potential. Consider applying recommendations."
        elif savings_percent > 5:
            recommendation_level = "low"
            recommendation_text = "Minor optimization potential. Current settings are reasonable."
        else:
            recommendation_level = "optimal"
            recommendation_text = "Resources are well-optimized. No changes recommended."
        
        # Generate warnings if HPA target adjustment is significant
        hpa_adjustment_percent = ((adjusted_hpa_target - current_hpa_target) / current_hpa_target * 100) if current_hpa_target > 0 else 0
        
        warnings = []
        if abs(hpa_adjustment_percent) > 50:
            warnings.append(
                f"⚠️ HPA target will change significantly ({current_hpa_target:.0f}% → {adjusted_hpa_target:.0f}%). "
                "This maintains the same scaling behavior with reduced requests."
            )
        
        if recommended_cpu_request <= MIN_CPU_REQUEST:
            warnings.append(
                f"⚠️ CPU request set to minimum {MIN_CPU_REQUEST}m for HPA stability. "
                "Very low CPU requests cause scaling instability due to percentage fluctuations."
            )
        
        if adjusted_hpa_target > 150:
            warnings.append(
                "⚠️ Adjusted HPA target is very high (>150%). Consider if this is appropriate for your workload. "
                "High targets mean less aggressive scaling."
            )
        
        # Resource change detection warning
        cpu_change_percent = abs(recommended_cpu_request - current_cpu_request) / current_cpu_request * 100 if current_cpu_request > 0 else 0
        if cpu_change_percent > 30:
            warnings.append(
                f"⚠️ Large CPU request change ({cpu_change_percent:.0f}%). After applying, monitor for 24-48 hours. "
                "The autoscaler will automatically detect the change and adjust HPA targets to prevent false positive spikes."
            )
        
        # Memory reduction warning
        memory_change_percent = (current_memory_request - recommended_memory_request) / current_memory_request * 100 if current_memory_request > 0 else 0
        if memory_change_percent > 20:
            warnings.append(
                f"⚠️ Memory reduction recommended ({memory_change_percent:.0f}%). Be cautious - OOM kills are disruptive. "
                "Consider applying gradually and monitoring for memory pressure."
            )
        
        return {
            # Current state
            'current': {
                'cpu_request_millicores': int(current_cpu_request),
                'memory_request_mb': int(current_memory_request),
                'hpa_target_percent': round(current_hpa_target, 1),
                'scaling_threshold_millicores': round(current_scaling_threshold, 1),
                'cpu_utilization_percent': round(current_cpu_utilization, 1),
                'memory_utilization_percent': round(current_memory_utilization, 1),
                'monthly_cost_usd': round(current_monthly_cost, 2)
            },
            
            # Usage statistics
            'usage_stats': {
                'cpu_avg_millicores': round(avg_cpu_usage, 1),
                'cpu_p50_millicores': round(p50_cpu_usage, 1),
                'cpu_p95_millicores': round(p95_cpu_usage, 1),
                'cpu_p99_millicores': round(p99_cpu_usage, 1),
                'cpu_max_millicores': round(max_cpu_usage, 1),
                'memory_avg_mb': round(avg_memory_usage, 1),
                'memory_p95_mb': round(p95_memory_usage, 1),
                'memory_max_mb': round(max_memory_usage, 1)
            },
            
            # Recommended state
            'recommended': {
                'cpu_request_millicores': recommended_cpu_request,
                'memory_request_mb': recommended_memory_request,
                'hpa_target_percent': round(adjusted_hpa_target, 1),
                'scaling_threshold_millicores': round(current_scaling_threshold, 1),  # Same as current!
                'monthly_cost_usd': round(optimized_monthly_cost, 2)
            },
            
            # Savings
            'savings': {
                'monthly_savings_usd': round(monthly_savings, 2),
                'savings_percent': round(savings_percent, 1),
                'cpu_reduction_percent': round((1 - recommended_cpu_request / current_cpu_request) * 100, 1) if current_cpu_request > 0 else 0,
                'memory_reduction_percent': round((1 - recommended_memory_request / current_memory_request) * 100, 1) if current_memory_request > 0 else 0,
                'hpa_adjustment_percent': round(hpa_adjustment_percent, 1)
            },
            
            # Metadata
            'recommendation_level': recommendation_level,
            'recommendation_text': recommendation_text,
            'warnings': warnings,
            'data_points_analyzed': len(recent),
            'analysis_period_hours': hours,
            'avg_pod_count': round(avg_pod_count, 1),
            
            # Implementation guide
            'implementation': {
                'step1': f"Update Deployment: Set CPU request to {recommended_cpu_request}m, memory to {recommended_memory_request}Mi",
                'step2': f"Update HPA: Set target utilization to {int(adjusted_hpa_target)}%",
                'step3': "Monitor for 24-48 hours to ensure scaling behavior is correct",
                'step4': "Verify that scaling still triggers at the same CPU usage levels",
                'yaml_snippet': self._generate_yaml_snippet(
                    recommended_cpu_request,
                    recommended_memory_request,
                    adjusted_hpa_target
                )
            }
        }
    
    def _generate_yaml_snippet(self, cpu_request: int, memory_request: int, hpa_target: float) -> str:
        """Generate YAML snippet for applying recommendations (no limits to avoid OOM/throttling)"""
        return f"""# Deployment resource requests (no limits - best practice for avoiding OOM/throttling)
resources:
  requests:
    cpu: {cpu_request}m
    memory: {memory_request}Mi
  # No limits - allows bursting without OOM kills or CPU throttling

---
# HPA configuration
spec:
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: {int(hpa_target)}"""
    
    def analyze_costs(self, deployment: str, hours: int = 24) -> Optional[CostMetrics]:
        """Analyze cost efficiency with detailed CPU and memory breakdown"""
        recent = self.db.get_recent_metrics(deployment, hours=hours)
        
        if len(recent) < 10:
            return None
        
        # Calculate averages
        avg_pod_count = statistics.mean([s.pod_count for s in recent])
        avg_utilization = statistics.mean([s.node_utilization for s in recent])
        avg_cpu_request = statistics.mean([s.cpu_request for s in recent]) / 1000.0  # Convert to cores
        avg_cpu_usage = statistics.mean([s.pod_cpu_usage for s in recent])  # Already in cores
        
        # Handle memory metrics with empty list protection
        memory_requests = [s.memory_request for s in recent if s.memory_request > 0]
        avg_memory_request = statistics.mean(memory_requests) if memory_requests else 512  # MB
        memory_usages = [s.memory_usage for s in recent if s.memory_usage > 0]
        avg_memory_usage = statistics.mean(memory_usages) if memory_usages else 0.0  # MB
        
        # Calculate runtime hours (based on data points and check interval)
        # Assuming metrics are collected every CHECK_INTERVAL seconds
        import os
        check_interval = int(os.getenv('CHECK_INTERVAL', '60'))
        runtime_hours = (len(recent) * check_interval) / 3600.0  # Convert to hours
        
        # CPU cost calculation
        cpu_requested_cores = avg_pod_count * avg_cpu_request
        cpu_used_cores = avg_pod_count * avg_cpu_usage
        cpu_cost = cpu_requested_cores * self.cost_per_vcpu_hour * runtime_hours
        
        # Memory cost calculation (convert MB to GB)
        memory_requested_gb = (avg_pod_count * avg_memory_request) / 1024.0
        memory_used_gb = (avg_pod_count * avg_memory_usage) / 1024.0
        memory_cost = memory_requested_gb * self.cost_per_gb_memory_hour * runtime_hours
        
        # Total cost
        total_cost = cpu_cost + memory_cost
        
        # Calculate utilization percentages
        cpu_utilization_percent = (cpu_used_cores / cpu_requested_cores * 100) if cpu_requested_cores > 0 else 0
        memory_utilization_percent = (memory_used_gb / memory_requested_gb * 100) if memory_requested_gb > 0 else 0
        
        # Wasted cost calculation (when low utilization but high request)
        wasted_cpu_cores = max(0, cpu_requested_cores - cpu_used_cores)
        wasted_memory_gb = max(0, memory_requested_gb - memory_used_gb)
        
        wasted_cpu_cost = wasted_cpu_cores * self.cost_per_vcpu_hour * runtime_hours
        wasted_memory_cost = wasted_memory_gb * self.cost_per_gb_memory_hour * runtime_hours
        total_wasted_cost = wasted_cpu_cost + wasted_memory_cost
        
        # Overall wasted capacity percentage
        requested_capacity = cpu_requested_cores
        wasted_capacity = wasted_cpu_cores
        wasted_percent = (wasted_capacity / requested_capacity * 100) if requested_capacity > 0 else 0
        
        # Monthly projections (extrapolate from runtime hours)
        hours_per_month = 730
        monthly_cpu_cost = cpu_requested_cores * self.cost_per_vcpu_hour * hours_per_month
        monthly_memory_cost = memory_requested_gb * self.cost_per_gb_memory_hour * hours_per_month
        monthly_cost = monthly_cpu_cost + monthly_memory_cost
        
        # Optimization potential
        optimal_cpu_cores = cpu_used_cores * 1.2  # 20% buffer
        optimal_memory_gb = memory_used_gb * 1.2
        optimal_cpu_cost = optimal_cpu_cores * self.cost_per_vcpu_hour * hours_per_month
        optimal_memory_cost = optimal_memory_gb * self.cost_per_gb_memory_hour * hours_per_month
        optimal_total_cost = optimal_cpu_cost + optimal_memory_cost
        optimization_potential = monthly_cost - optimal_total_cost
        
        # Generate recommendation
        if wasted_percent > 40 or cpu_utilization_percent < 30:
            recommendation = (
                f"High waste detected. CPU utilization: {cpu_utilization_percent:.1f}%, "
                f"Memory utilization: {memory_utilization_percent:.1f}%. "
                f"Consider reducing CPU request from {int(avg_cpu_request*1000)}m to {int(avg_cpu_usage*1000*1.2)}m, "
                f"and memory from {int(avg_memory_request)}MB to {int(avg_memory_usage*1.2)}MB"
            )
        elif wasted_percent > 25 or cpu_utilization_percent < 50:
            recommendation = (
                f"Moderate waste. CPU: {cpu_utilization_percent:.1f}%, Memory: {memory_utilization_percent:.1f}%. "
                f"Could save ${optimization_potential:.2f}/month"
            )
        elif avg_utilization < 50:
            recommendation = "Low node utilization. Consider increasing HPA target"
        else:
            recommendation = "Well-optimized"
        
        metrics = CostMetrics(
            deployment=deployment,
            avg_pod_count=avg_pod_count,
            avg_utilization=avg_utilization,
            wasted_capacity_percent=wasted_percent,
            estimated_monthly_cost=monthly_cost,
            optimization_potential=max(0, optimization_potential),
            recommendation=recommendation,
            cpu_cost=cpu_cost,
            memory_cost=memory_cost,
            total_cost=total_cost,
            wasted_cpu_cost=wasted_cpu_cost,
            wasted_memory_cost=wasted_memory_cost,
            total_wasted_cost=total_wasted_cost,
            cpu_utilization_percent=cpu_utilization_percent,
            memory_utilization_percent=memory_utilization_percent,
            runtime_hours=runtime_hours
        )
        
        if optimization_potential > 50:
            self.alert_manager.send_alert(
                title=f"Cost Optimization: {deployment}",
                message=recommendation,
                severity="info",
                fields={
                    "Monthly Cost": f"${monthly_cost:.2f}",
                    "Potential Savings": f"${optimization_potential:.2f}",
                    "Wasted Capacity": f"{wasted_percent:.1f}%",
                    "CPU Utilization": f"{cpu_utilization_percent:.1f}%",
                    "Memory Utilization": f"{memory_utilization_percent:.1f}%"
                }
            )
        
        return metrics
    
    def detect_memory_leak(self, deployment: str, hours: int = 24) -> Optional[Dict]:
        """
        Detect potential memory leaks by analyzing memory usage trends.
        
        Memory leak indicators:
        1. Continuous upward trend in memory usage
        2. Memory usage grows faster than pod restarts can reset
        3. Memory usage approaches request limit over time
        
        Args:
            deployment: Deployment name
            hours: Hours of historical data to analyze
        
        Returns:
            Dict with leak detection results or None if insufficient data
        """
        recent = self.db.get_recent_metrics(deployment, hours=hours)
        
        if len(recent) < 30:  # Need at least 30 data points
            return None
        
        # Extract memory usage over time (sorted by timestamp)
        memory_data = [
            (m.timestamp, m.memory_usage, m.memory_request)
            for m in sorted(recent, key=lambda x: x.timestamp)
            if m.memory_usage > 0 and m.memory_request > 0
        ]
        
        if len(memory_data) < 20:
            return None
        
        timestamps = [m[0] for m in memory_data]
        memory_usages = [m[1] for m in memory_data]
        memory_requests = [m[2] for m in memory_data]
        
        avg_request = statistics.mean(memory_requests)
        
        # Calculate linear regression slope for memory trend
        n = len(memory_usages)
        x = list(range(n))
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(memory_usages)
        
        numerator = sum((x[i] - x_mean) * (memory_usages[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return None
        
        slope = numerator / denominator  # MB per data point
        
        # Calculate R-squared to see how well the trend fits
        ss_res = sum((memory_usages[i] - (y_mean + slope * (x[i] - x_mean))) ** 2 for i in range(n))
        ss_tot = sum((memory_usages[i] - y_mean) ** 2 for i in range(n))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # Calculate memory growth rate (MB per hour)
        # Assuming data points are roughly evenly spaced
        time_span_hours = (timestamps[-1] - timestamps[0]).total_seconds() / 3600
        if time_span_hours > 0:
            growth_rate_per_hour = (slope * n) / time_span_hours
        else:
            growth_rate_per_hour = 0
        
        # Calculate current utilization percentage
        current_usage = memory_usages[-1]
        current_utilization = (current_usage / avg_request * 100) if avg_request > 0 else 0
        
        # Detect leak based on multiple criteria
        is_leak = False
        leak_severity = "none"
        leak_confidence = 0.0
        reasons = []
        
        # Criterion 1: Positive slope with good fit (R² > 0.5)
        if slope > 0 and r_squared > 0.5:
            reasons.append(f"Continuous upward trend (R²={r_squared:.2f})")
            leak_confidence += 0.3
        
        # Criterion 2: Significant growth rate (>1% of request per hour)
        growth_percent_per_hour = (growth_rate_per_hour / avg_request * 100) if avg_request > 0 else 0
        if growth_percent_per_hour > 1:
            reasons.append(f"Growing {growth_percent_per_hour:.1f}%/hour")
            leak_confidence += 0.3
        
        # Criterion 3: Memory approaching limit (>80% utilization with upward trend)
        if current_utilization > 80 and slope > 0:
            reasons.append(f"High utilization ({current_utilization:.0f}%) with upward trend")
            leak_confidence += 0.2
        
        # Criterion 4: Compare first half vs second half average
        first_half_avg = statistics.mean(memory_usages[:n//2])
        second_half_avg = statistics.mean(memory_usages[n//2:])
        half_growth = ((second_half_avg - first_half_avg) / first_half_avg * 100) if first_half_avg > 0 else 0
        
        if half_growth > 10:  # >10% growth between halves
            reasons.append(f"Memory grew {half_growth:.0f}% over analysis period")
            leak_confidence += 0.2
        
        # Determine severity
        if leak_confidence >= 0.7:
            is_leak = True
            leak_severity = "high"
        elif leak_confidence >= 0.5:
            is_leak = True
            leak_severity = "medium"
        elif leak_confidence >= 0.3:
            is_leak = True
            leak_severity = "low"
        
        # Estimate time to OOM (if leak detected)
        time_to_oom_hours = None
        if is_leak and growth_rate_per_hour > 0:
            remaining_memory = avg_request - current_usage
            if remaining_memory > 0:
                time_to_oom_hours = remaining_memory / growth_rate_per_hour
        
        result = {
            'deployment': deployment,
            'is_leak_detected': is_leak,
            'leak_severity': leak_severity,
            'leak_confidence': round(leak_confidence, 2),
            'reasons': reasons,
            'analysis': {
                'slope_mb_per_point': round(slope, 3),
                'r_squared': round(r_squared, 3),
                'growth_rate_mb_per_hour': round(growth_rate_per_hour, 2),
                'growth_percent_per_hour': round(growth_percent_per_hour, 2),
                'current_usage_mb': round(current_usage, 1),
                'avg_request_mb': round(avg_request, 1),
                'current_utilization_percent': round(current_utilization, 1),
                'first_half_avg_mb': round(first_half_avg, 1),
                'second_half_avg_mb': round(second_half_avg, 1),
                'data_points': n,
                'analysis_hours': round(time_span_hours, 1)
            },
            'time_to_oom_hours': round(time_to_oom_hours, 1) if time_to_oom_hours else None,
            'recommendation': self._get_leak_recommendation(is_leak, leak_severity, time_to_oom_hours)
        }
        
        # Send alert if leak detected
        if is_leak and leak_severity in ['high', 'medium']:
            self.alert_manager.send_alert(
                title=f"⚠️ Memory Leak Detected: {deployment}",
                message=f"Severity: {leak_severity.upper()}. {', '.join(reasons)}",
                severity="warning" if leak_severity == "medium" else "critical",
                fields={
                    "Current Usage": f"{current_usage:.0f}MB / {avg_request:.0f}MB ({current_utilization:.0f}%)",
                    "Growth Rate": f"{growth_rate_per_hour:.1f}MB/hour ({growth_percent_per_hour:.1f}%/hour)",
                    "Time to OOM": f"{time_to_oom_hours:.1f} hours" if time_to_oom_hours else "N/A",
                    "Confidence": f"{leak_confidence:.0%}"
                }
            )
        
        return result
    
    def _get_leak_recommendation(self, is_leak: bool, severity: str, time_to_oom: Optional[float]) -> str:
        """Generate recommendation based on leak detection results"""
        if not is_leak:
            return "No memory leak detected. Memory usage is stable."
        
        if severity == "high":
            if time_to_oom and time_to_oom < 24:
                return f"🚨 CRITICAL: Memory leak detected! Estimated OOM in {time_to_oom:.0f} hours. Immediate action required - consider restarting pods or investigating the leak."
            return "🔴 HIGH: Strong memory leak pattern detected. Investigate application for memory leaks. Consider increasing memory request temporarily while fixing."
        elif severity == "medium":
            return "🟡 MEDIUM: Possible memory leak detected. Monitor closely and investigate if trend continues. Check for unclosed connections, caches, or event listeners."
        else:
            return "🟢 LOW: Minor upward memory trend detected. May be normal behavior or early leak. Continue monitoring."
    
    def generate_weekly_report(self, deployments: List[str]):
        """Generate weekly cost report"""
        total_cost = 0
        total_savings = 0
        report_lines = ["📊 Weekly Cost Report\n"]
        
        for deployment in deployments:
            metrics = self.analyze_costs(deployment)
            if metrics:
                total_cost += metrics.estimated_monthly_cost
                total_savings += metrics.optimization_potential
                report_lines.append(f"• {deployment}: ${metrics.estimated_monthly_cost:.2f}/month (save ${metrics.optimization_potential:.2f})")
        
        report_lines.append(f"\n💰 Total: ${total_cost:.2f}")
        report_lines.append(f"💡 Savings: ${total_savings:.2f}")
        
        self.alert_manager.send_alert(
            title="Weekly Cost Report",
            message="\n".join(report_lines),
            severity="info",
            fields={"Total Cost": f"${total_cost:.2f}", "Savings": f"${total_savings:.2f}"}
        )


class PredictiveScaler:
    """Predictive scaling with validation and adaptive learning"""
    
    def __init__(self, db: TimeSeriesDatabase, pattern_recognizer: PatternRecognizer, alert_manager: AlertManager):
        self.db = db
        self.pattern_recognizer = pattern_recognizer
        self.alert_manager = alert_manager
        self.min_accuracy_threshold = float(os.getenv('PREDICTION_MIN_ACCURACY', '0.60'))  # 60% accuracy required
        self.min_predictions_for_trust = int(os.getenv('PREDICTION_MIN_SAMPLES', '10'))  # Need 10 predictions
    
    def get_adaptive_confidence(self, deployment: str, base_confidence: float) -> float:
        """
        Adjust confidence based on historical prediction accuracy
        Reduces confidence if predictions have been inaccurate
        """
        accuracy_stats = self.db.get_prediction_accuracy(deployment)
        
        if not accuracy_stats:
            # No history yet, use base confidence but reduce it slightly
            return base_confidence * 0.9
        
        accuracy_rate = accuracy_stats['accuracy_rate'] / 100.0
        false_positive_rate = accuracy_stats['false_positive_rate'] / 100.0
        total = accuracy_stats['total_predictions']
        
        # Need minimum samples before trusting
        if total < self.min_predictions_for_trust:
            return base_confidence * 0.8  # Reduce confidence until we have enough data
        
        # Adjust confidence based on accuracy
        # If accuracy is low, reduce confidence significantly
        if accuracy_rate < self.min_accuracy_threshold:
            adjusted = base_confidence * accuracy_rate
            logger.warning(
                f"{deployment} - Low prediction accuracy ({accuracy_rate:.0%}), "
                f"reducing confidence from {base_confidence:.0%} to {adjusted:.0%}"
            )
            return adjusted
        
        # If false positive rate is high, reduce confidence for scale-up predictions
        if false_positive_rate > 0.3:  # More than 30% false positives
            adjusted = base_confidence * (1.0 - false_positive_rate * 0.5)
            logger.warning(
                f"{deployment} - High false positive rate ({false_positive_rate:.0%}), "
                f"reducing confidence to {adjusted:.0%}"
            )
            return adjusted
        
        # Good accuracy, use base confidence
        return base_confidence
    
    def should_trust_prediction(self, deployment: str, action: str) -> bool:
        """
        Determine if we should trust this prediction based on historical accuracy
        """
        accuracy_stats = self.db.get_prediction_accuracy(deployment)
        
        if not accuracy_stats:
            # No history, be conservative
            return False
        
        total = accuracy_stats['total_predictions']
        accuracy_rate = accuracy_stats['accuracy_rate'] / 100.0
        false_positive_rate = accuracy_stats['false_positive_rate'] / 100.0
        
        # Need minimum samples
        if total < self.min_predictions_for_trust:
            return False
        
        # Don't trust if accuracy is too low
        if accuracy_rate < self.min_accuracy_threshold:
            return False
        
        # Don't trust scale-up predictions if false positive rate is high
        if action == "pre_scale_up" and false_positive_rate > 0.4:
            logger.warning(
                f"{deployment} - High false positive rate ({false_positive_rate:.0%}), "
                "skipping predictive scale-up"
            )
            return False
        
        return True
    
    def predict_and_recommend(self, deployment: str, current_target: int) -> Optional[Prediction]:
        """Predict and recommend with adaptive learning"""
        # Validate previous predictions first
        self.db.validate_predictions(deployment, hours_back=2)
        
        predicted_cpu, base_confidence = self.pattern_recognizer.predict_next_hour(deployment)
        
        if base_confidence < 0.5:
            return None
        
        # Get adaptive confidence based on historical accuracy
        adaptive_confidence = self.get_adaptive_confidence(deployment, base_confidence)
        
        # Determine action
        if predicted_cpu > 80:
            action = "pre_scale_up"
            reasoning = f"Predicted {predicted_cpu:.1f}% > 80% - pre-scale up"
            recommended_target = max(50, current_target - 10)
        elif predicted_cpu < 50:
            action = "scale_down"
            reasoning = f"Predicted {predicted_cpu:.1f}% < 50% - scale down"
            recommended_target = min(80, current_target + 10)
        else:
            action = "maintain"
            reasoning = f"Predicted {predicted_cpu:.1f}% in normal range"
            recommended_target = current_target
        
        # Check if we should trust this prediction
        if action == "pre_scale_up" and not self.should_trust_prediction(deployment, action):
            logger.info(
                f"{deployment} - Prediction suggests scale-up but historical accuracy is low, "
                "skipping to prevent false positive"
            )
            # Still store prediction for learning, but don't act on it
            action = "maintain"
            reasoning = f"Predicted {predicted_cpu:.1f}% but low historical accuracy - maintaining"
            recommended_target = current_target
        
        prediction = Prediction(
            timestamp=datetime.now(),
            deployment=deployment,
            predicted_cpu=predicted_cpu,
            confidence=adaptive_confidence,  # Use adaptive confidence
            recommended_action=action,
            reasoning=reasoning
        )
        
        self.db.store_prediction(prediction)
        
        # Log accuracy stats if available
        accuracy_stats = self.db.get_prediction_accuracy(deployment)
        if accuracy_stats:
            logger.debug(
                f"{deployment} - Prediction accuracy: {accuracy_stats['accuracy_rate']:.1f}% "
                f"({accuracy_stats['accurate_predictions']}/{accuracy_stats['total_predictions']}), "
                f"False positives: {accuracy_stats['false_positive_rate']:.1f}%"
            )
        
        if action == "pre_scale_up" and adaptive_confidence > 0.7:
            self.alert_manager.send_alert(
                title=f"Predictive Scaling: {deployment}",
                message=reasoning,
                severity="info",
                fields={
                    "Predicted CPU": f"{predicted_cpu:.1f}%",
                    "Confidence": f"{adaptive_confidence:.0%}",
                    "Recommended": f"{recommended_target}%",
                    "Historical Accuracy": f"{accuracy_stats['accuracy_rate']:.1f}%" if accuracy_stats else "N/A"
                }
            )
        
        return prediction


class AutoTuner:
    """
    Auto-tune HPA targets based on historical performance with adaptive learning.
    
    Features:
    - Learns optimal HPA targets from historical data
    - Bayesian optimization for faster initial learning
    - Per-hour optimal targets (different for peak vs off-peak)
    - Adaptive learning rate based on stability
    - Tracks performance per target value
    - Automatic application when confidence is high
    """
    
    def __init__(self, db: TimeSeriesDatabase, alert_manager: AlertManager):
        self.db = db
        self.alert_manager = alert_manager
        
        # Adaptive learning parameters
        self.learning_rate = 0.1  # Start conservative
        self.min_learning_rate = 0.05
        self.max_learning_rate = 0.3
        self.stability_window = []  # Track recent stability
        self.stability_window_size = 20
        
        # Performance tracking
        self.target_performance: Dict[str, Dict[int, List[float]]] = {}  # deployment -> target -> utilizations
        
        # Per-hour optimal targets
        self.hourly_targets: Dict[str, Dict[int, Tuple[int, float]]] = {}  # deployment -> hour -> (target, confidence)
        
        # Bayesian optimization state
        self.bayesian_state: Dict[str, Dict] = {}  # deployment -> optimization state
        self.exploration_rate = 0.2  # 20% exploration, 80% exploitation
    
    def _init_bayesian_state(self, deployment: str):
        """Initialize Bayesian optimization state for a deployment"""
        if deployment not in self.bayesian_state:
            self.bayesian_state[deployment] = {
                'observations': [],  # List of (target, score) tuples
                'best_target': 70,
                'best_score': 0.0,
                'iteration': 0,
                'prior_mean': 70,  # Prior belief: 70% is a good starting point
                'prior_std': 15,   # Uncertainty in prior
            }
    
    def bayesian_suggest_target(self, deployment: str) -> int:
        """
        Use Bayesian optimization to suggest next target to try.
        
        Balances exploration (trying new targets) vs exploitation (using known good targets).
        
        Returns:
            Suggested HPA target percentage
        """
        self._init_bayesian_state(deployment)
        state = self.bayesian_state[deployment]
        
        import random
        
        # Exploration vs exploitation
        if random.random() < self.exploration_rate or len(state['observations']) < 5:
            # Exploration: sample from prior with some noise
            suggested = int(random.gauss(state['prior_mean'], state['prior_std']))
            suggested = max(40, min(90, suggested))  # Clamp to valid range
            logger.debug(f"{deployment} - Bayesian exploration: suggesting {suggested}%")
        else:
            # Exploitation: use best known target with small perturbation
            perturbation = random.gauss(0, 3)
            suggested = int(state['best_target'] + perturbation)
            suggested = max(40, min(90, suggested))
            logger.debug(f"{deployment} - Bayesian exploitation: suggesting {suggested}% (best: {state['best_target']}%)")
        
        return suggested
    
    def bayesian_update(self, deployment: str, target: int, score: float):
        """
        Update Bayesian optimization state with new observation.
        
        Args:
            deployment: Deployment name
            target: HPA target that was used
            score: Performance score (higher is better)
        """
        self._init_bayesian_state(deployment)
        state = self.bayesian_state[deployment]
        
        # Add observation
        state['observations'].append((target, score))
        state['iteration'] += 1
        
        # Update best if this is better
        if score > state['best_score']:
            state['best_target'] = target
            state['best_score'] = score
            logger.info(f"{deployment} - Bayesian: new best target {target}% (score: {score:.2f})")
        
        # Update prior based on observations (simple moving average)
        if len(state['observations']) >= 3:
            recent_obs = state['observations'][-10:]  # Last 10 observations
            weighted_sum = sum(t * s for t, s in recent_obs)
            weight_total = sum(s for _, s in recent_obs)
            if weight_total > 0:
                state['prior_mean'] = weighted_sum / weight_total
            
            # Reduce uncertainty as we learn
            state['prior_std'] = max(5, state['prior_std'] * 0.95)
        
        # Reduce exploration rate over time
        self.exploration_rate = max(0.05, self.exploration_rate * 0.99)
    
    def learn_hourly_targets(self, deployment: str) -> Dict[int, Tuple[int, float]]:
        """
        Learn optimal targets for each hour of the day.
        
        Different hours may have different optimal targets:
        - Peak hours: lower target for faster response
        - Off-peak hours: higher target for cost savings
        
        Returns:
            Dict mapping hour -> (optimal_target, confidence)
        """
        hourly_targets = {}
        
        # Get 7 days of historical data
        recent = self.db.get_recent_metrics(deployment, hours=168)
        
        if len(recent) < 100:
            return hourly_targets
        
        # Group metrics by hour
        hourly_metrics: Dict[int, List] = defaultdict(list)
        for snapshot in recent:
            if not snapshot.scheduling_spike:
                hour = snapshot.timestamp.hour
                hourly_metrics[hour].append({
                    'target': snapshot.hpa_target,
                    'utilization': snapshot.node_utilization,
                    'confidence': snapshot.confidence
                })
        
        # Find optimal target for each hour
        for hour, metrics in hourly_metrics.items():
            if len(metrics) < 5:
                continue
            
            # Group by target
            target_scores: Dict[int, List[float]] = defaultdict(list)
            for m in metrics:
                target = int(m['target'])
                # Score: how close to ideal utilization (65%) with good confidence
                ideal_util = 65
                util_score = max(0, 1 - abs(m['utilization'] - ideal_util) / 50)
                conf_score = m['confidence']
                score = util_score * 0.7 + conf_score * 0.3
                target_scores[target].append(score)
            
            # Find best target for this hour
            best_target = None
            best_avg_score = 0
            
            for target, scores in target_scores.items():
                if len(scores) >= 3:
                    avg_score = statistics.mean(scores)
                    if avg_score > best_avg_score:
                        best_avg_score = avg_score
                        best_target = target
            
            if best_target is not None:
                # Confidence based on sample count and score consistency
                sample_conf = min(1.0, len(target_scores[best_target]) / 20)
                score_std = statistics.stdev(target_scores[best_target]) if len(target_scores[best_target]) > 1 else 0.5
                consistency_conf = max(0.3, 1 - score_std)
                confidence = sample_conf * 0.5 + consistency_conf * 0.5
                
                hourly_targets[hour] = (best_target, confidence)
        
        # Cache results
        self.hourly_targets[deployment] = hourly_targets
        
        # Log summary
        if hourly_targets:
            peak_hours = [h for h, (t, c) in hourly_targets.items() if t < 65]
            offpeak_hours = [h for h, (t, c) in hourly_targets.items() if t >= 70]
            logger.info(
                f"{deployment} - Learned hourly targets: "
                f"peak hours ({len(peak_hours)}): {sorted(peak_hours)}, "
                f"off-peak hours ({len(offpeak_hours)}): {sorted(offpeak_hours)}"
            )
        
        return hourly_targets
    
    def get_hourly_target(self, deployment: str, hour: Optional[int] = None) -> Optional[Tuple[int, float]]:
        """
        Get optimal target for a specific hour.
        
        Args:
            deployment: Deployment name
            hour: Hour of day (0-23), defaults to current hour
        
        Returns:
            Tuple of (target, confidence) or None
        """
        if hour is None:
            hour = datetime.now().hour
        
        # Check cache
        if deployment in self.hourly_targets and hour in self.hourly_targets[deployment]:
            return self.hourly_targets[deployment][hour]
        
        # Learn if not cached
        hourly_targets = self.learn_hourly_targets(deployment)
        return hourly_targets.get(hour)
    
    def adjust_learning_rate(self, deployment: str):
        """
        Adjust learning rate based on recent stability.
        
        Stable workloads (low variance) can learn faster.
        Unstable workloads (high variance) should learn slower.
        
        Args:
            deployment: Deployment name
        """
        try:
            # Get recent HPA target changes
            recent = self.db.get_recent_metrics(deployment, hours=24)
            
            if len(recent) < 10:
                return  # Not enough data
            
            # Calculate variance in HPA targets
            targets = [m.hpa_target for m in recent if m.hpa_target > 0]
            
            if len(targets) < 10:
                return
            
            variance = statistics.variance(targets) if len(targets) > 1 else 0
            
            # Update stability window
            self.stability_window.append(variance)
            if len(self.stability_window) > self.stability_window_size:
                self.stability_window.pop(0)
            
            # Calculate average variance
            avg_variance = statistics.mean(self.stability_window) if self.stability_window else variance
            
            # Adjust learning rate based on stability
            old_rate = self.learning_rate
            
            if avg_variance < 5:  # Very stable (variance < 5%)
                # Increase learning rate (learn faster)
                self.learning_rate = min(self.max_learning_rate, self.learning_rate * 1.2)
            elif avg_variance > 20:  # Unstable (variance > 20%)
                # Decrease learning rate (learn slower)
                self.learning_rate = max(self.min_learning_rate, self.learning_rate * 0.8)
            elif avg_variance > 10:  # Moderately unstable
                # Slightly decrease
                self.learning_rate = max(self.min_learning_rate, self.learning_rate * 0.95)
            
            # Log if changed significantly
            if abs(self.learning_rate - old_rate) > 0.01:
                logger.info(
                    f"{deployment} - Learning rate adjusted: {old_rate:.3f} → {self.learning_rate:.3f} "
                    f"(variance: {avg_variance:.1f})"
                )
        
        except Exception as e:
            logger.debug(f"Error adjusting learning rate: {e}")
    
    def track_target_performance(self, deployment: str, target: int, utilization: float):
        """
        Track performance for a specific HPA target.
        
        Args:
            deployment: Deployment name
            target: HPA target percentage
            utilization: Actual node utilization achieved
        """
        if deployment not in self.target_performance:
            self.target_performance[deployment] = {}
        
        if target not in self.target_performance[deployment]:
            self.target_performance[deployment][target] = []
        
        # Keep last 100 samples per target
        perf_list = self.target_performance[deployment][target]
        perf_list.append(utilization)
        if len(perf_list) > 100:
            perf_list.pop(0)
        
        # Update Bayesian optimization
        ideal_util = 65
        score = max(0, 1 - abs(utilization - ideal_util) / 50)
        self.bayesian_update(deployment, target, score)
    
    def find_optimal_target(self, deployment: str) -> Optional[Tuple[int, float]]:
        """
        Find optimal HPA target with adaptive learning and Bayesian optimization.
        
        Args:
            deployment: Deployment name
        
        Returns:
            Tuple of (optimal_target, confidence) or None
        """
        # Adjust learning rate based on stability
        self.adjust_learning_rate(deployment)
        
        # Check for hourly-specific target first
        hourly_target = self.get_hourly_target(deployment)
        if hourly_target and hourly_target[1] > 0.7:
            logger.info(
                f"{deployment} - Using hourly target for hour {datetime.now().hour}: "
                f"{hourly_target[0]}% (confidence: {hourly_target[1]:.0%})"
            )
            return hourly_target
        
        # Get historical data
        recent = self.db.get_recent_metrics(deployment, hours=168)
        
        if len(recent) < 100:
            # Not enough data - use Bayesian suggestion
            suggested = self.bayesian_suggest_target(deployment)
            logger.info(f"{deployment} - Insufficient data, Bayesian suggests: {suggested}%")
            return suggested, 0.5
        
        target_performance: Dict[int, list] = defaultdict(list)
        
        for snapshot in recent:
            if not snapshot.scheduling_spike:
                target = int(snapshot.hpa_target)
                target_performance[target].append({
                    'utilization': snapshot.node_utilization,
                    'confidence': snapshot.confidence
                })
                
                # Track performance
                self.track_target_performance(
                    deployment,
                    target,
                    snapshot.node_utilization
                )
        
        best_target = None
        best_score = -1
        
        for target, samples in target_performance.items():
            if len(samples) < 10:
                continue
            
            avg_util = statistics.mean([s['utilization'] for s in samples])
            avg_conf = statistics.mean([s['confidence'] for s in samples])
            util_stddev = statistics.stdev([s['utilization'] for s in samples])
            
            target_score = 65
            util_penalty = abs(avg_util - target_score)
            
            # Use learning rate to weight stability importance
            # Higher learning rate = less penalty for variance (more confident in stable systems)
            stability_bonus = max(0, 10 - util_stddev) * (1.0 + self.learning_rate)
            confidence_bonus = avg_conf * 10
            
            score = 100 - util_penalty + stability_bonus + confidence_bonus
            
            if score > best_score:
                best_score = score
                best_target = target
        
        if best_target is not None:
            # Confidence includes learning rate factor
            base_confidence = best_score / 100.0
            learning_confidence = self.learning_rate / self.max_learning_rate
            confidence = (base_confidence * 0.8 + learning_confidence * 0.2)
            
            self.db.update_optimal_target(deployment, int(best_target), confidence)
            logger.info(
                f"{deployment} - Optimal target: {best_target}% "
                f"(confidence: {confidence:.0%}, learning_rate: {self.learning_rate:.3f})"
            )
            return int(best_target), confidence
        
        return None
    
    def get_learning_stats(self, deployment: str) -> Dict:
        """
        Get learning statistics for a deployment.
        
        Args:
            deployment: Deployment name
        
        Returns:
            Dictionary with learning statistics
        """
        stats = {
            'learning_rate': round(self.learning_rate, 3),
            'stability_window_size': len(self.stability_window),
            'avg_variance': round(statistics.mean(self.stability_window), 2) if self.stability_window else 0,
            'targets_tracked': 0,
            'total_samples': 0,
            'exploration_rate': round(self.exploration_rate, 3),
            'hourly_targets_learned': 0
        }
        
        if deployment in self.target_performance:
            stats['targets_tracked'] = len(self.target_performance[deployment])
            stats['total_samples'] = sum(
                len(samples) for samples in self.target_performance[deployment].values()
            )
        
        if deployment in self.hourly_targets:
            stats['hourly_targets_learned'] = len(self.hourly_targets[deployment])
        
        if deployment in self.bayesian_state:
            state = self.bayesian_state[deployment]
            stats['bayesian_iterations'] = state['iteration']
            stats['bayesian_best_target'] = state['best_target']
            stats['bayesian_best_score'] = round(state['best_score'], 3)
        
        return stats
