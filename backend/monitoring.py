"""
Performance monitoring and metrics collection module.

Tracks system performance metrics including:
- Request latency (ms)
- Throughput (requests/sec)
- Error rate (%)
- API endpoint performance
- Data processing time
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict, deque
import json
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Tracks performance metrics for a specific operation"""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.end_time = None
        self.duration_ms = 0
        self.status = 'pending'  # pending, success, error
        self.error_message = None
        self.timestamp = datetime.utcnow()
    
    def start(self):
        """Mark operation start"""
        self.start_time = time.time()
    
    def end(self, status: str = 'success', error_msg: str = None):
        """Mark operation end and calculate duration"""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.status = status
        self.error_message = error_msg
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for logging/storage"""
        return {
            'operation': self.operation_name,
            'timestamp': self.timestamp.isoformat(),
            'duration_ms': round(self.duration_ms, 2),
            'status': self.status,
            'error': self.error_message
        }


class PerformanceMonitor:
    """
    Collects and aggregates performance metrics.
    
    Tracks:
    - Latency: Response time per operation (ms)
    - Throughput: Operations per second
    - Error rate: Percentage of failed operations
    """
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize performance monitor.
        
        Args:
            max_history: Maximum metrics to keep in memory (FIFO)
        """
        self.max_history = max_history
        self.metrics_history = deque(maxlen=max_history)
        self.operation_counts = defaultdict(int)
        self.operation_errors = defaultdict(int)
        self.operation_times = defaultdict(list)
        self.start_time = datetime.utcnow()
    
    def record_operation(self, metric: PerformanceMetrics):
        """Record a completed operation"""
        self.metrics_history.append(metric)
        self.operation_counts[metric.operation_name] += 1
        self.operation_times[metric.operation_name].append(metric.duration_ms)
        
        if metric.status == 'error':
            self.operation_errors[metric.operation_name] += 1
    
    def get_latency_ms(self, operation: str = None) -> float:
        """
        Get average latency in milliseconds.
        
        Args:
            operation: Specific operation, or None for all operations
            
        Returns:
            Average latency in ms
        """
        if operation:
            times = self.operation_times.get(operation, [])
            if not times:
                return 0.0
            return sum(times) / len(times)
        
        all_times = [t for times in self.operation_times.values() for t in times]
        if not all_times:
            return 0.0
        return sum(all_times) / len(all_times)
    
    def get_throughput(self, operation: str = None, time_window_seconds: int = 60) -> float:
        """
        Get throughput (operations per second).
        
        Args:
            operation: Specific operation, or None for all operations
            time_window_seconds: Time window for calculation (default 60 seconds)
            
        Returns:
            Operations per second
        """
        cutoff_time = datetime.utcnow() - timedelta(seconds=time_window_seconds)
        
        if operation:
            count = sum(1 for m in self.metrics_history 
                       if m.operation_name == operation and m.timestamp > cutoff_time)
        else:
            count = sum(1 for m in self.metrics_history if m.timestamp > cutoff_time)
        
        if time_window_seconds == 0:
            return 0.0
        return count / time_window_seconds
    
    def get_error_rate(self, operation: str = None) -> float:
        """
        Get error rate as percentage.
        
        Args:
            operation: Specific operation, or None for all operations
            
        Returns:
            Error rate as percentage (0-100)
        """
        if operation:
            total = self.operation_counts.get(operation, 0)
            errors = self.operation_errors.get(operation, 0)
        else:
            total = sum(self.operation_counts.values())
            errors = sum(self.operation_errors.values())
        
        if total == 0:
            return 0.0
        return (errors / total) * 100
    
    def get_metrics_summary(self) -> Dict:
        """Get comprehensive metrics summary"""
        total_ops = sum(self.operation_counts.values())
        total_errors = sum(self.operation_errors.values())
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        
        operation_details = {}
        for op_name in self.operation_counts.keys():
            operation_details[op_name] = {
                'count': self.operation_counts[op_name],
                'errors': self.operation_errors[op_name],
                'error_rate': self.get_error_rate(op_name),
                'avg_latency_ms': round(self.get_latency_ms(op_name), 2),
                'throughput_ops_sec': round(self.get_throughput(op_name), 4)
            }
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'uptime_seconds': round(uptime, 2),
            'total_operations': total_ops,
            'total_errors': total_errors,
            'overall_error_rate': round(self.get_error_rate(), 2),
            'overall_latency_ms': round(self.get_latency_ms(), 2),
            'overall_throughput_ops_sec': round(self.get_throughput(), 4),
            'operations': operation_details,
            'metrics_retained': len(self.metrics_history)
        }


class MonitoringDatabase:
    """Persists monitoring data to SQLite database"""
    
    def __init__(self, db_path: str = './data/monitoring.db'):
        """Initialize monitoring database"""
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Create monitoring tables if they don't exist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Performance metrics table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS performance_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        operation TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        duration_ms REAL NOT NULL,
                        status TEXT NOT NULL,
                        error TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # System health table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS system_health (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME NOT NULL,
                        uptime_seconds REAL NOT NULL,
                        total_operations INTEGER NOT NULL,
                        total_errors INTEGER NOT NULL,
                        error_rate REAL NOT NULL,
                        avg_latency_ms REAL NOT NULL,
                        throughput_ops_sec REAL NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create indices for faster queries
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_performance_timestamp 
                    ON performance_metrics(timestamp)
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_performance_operation 
                    ON performance_metrics(operation)
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_health_timestamp 
                    ON system_health(timestamp)
                ''')
                
                conn.commit()
                logger.info(f"Monitoring database initialized at {self.db_path}")
        
        except Exception as e:
            logger.error(f"Failed to initialize monitoring database: {str(e)}")
    
    def store_metric(self, metric: PerformanceMetrics):
        """Store a performance metric"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO performance_metrics 
                    (operation, timestamp, duration_ms, status, error)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    metric.operation_name,
                    metric.timestamp.isoformat(),
                    metric.duration_ms,
                    metric.status,
                    metric.error_message
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to store metric: {str(e)}")
    
    def store_health_snapshot(self, summary: Dict):
        """Store a system health snapshot"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO system_health
                    (timestamp, uptime_seconds, total_operations, total_errors, 
                     error_rate, avg_latency_ms, throughput_ops_sec)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    summary['timestamp'],
                    summary['uptime_seconds'],
                    summary['total_operations'],
                    summary['total_errors'],
                    summary['overall_error_rate'],
                    summary['overall_latency_ms'],
                    summary['overall_throughput_ops_sec']
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to store health snapshot: {str(e)}")
    
    def get_metrics_by_operation(self, operation: str, limit: int = 100) -> List[Dict]:
        """Retrieve metrics for a specific operation"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM performance_metrics
                    WHERE operation = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (operation, limit))
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to retrieve metrics: {str(e)}")
            return []
    
    def get_health_history(self, hours: int = 24, limit: int = 100) -> List[Dict]:
        """Retrieve system health history"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM system_health
                    WHERE timestamp > ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (cutoff_time.isoformat(), limit))
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to retrieve health history: {str(e)}")
            return []
    
    def cleanup_old_data(self, days: int = 7):
        """Remove metrics older than specified days"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    'DELETE FROM performance_metrics WHERE timestamp < ?',
                    (cutoff_time.isoformat(),)
                )
                
                cursor.execute(
                    'DELETE FROM system_health WHERE timestamp < ?',
                    (cutoff_time.isoformat(),)
                )
                
                deleted = cursor.rowcount
                conn.commit()
                logger.info(f"Cleaned up {deleted} old monitoring records")
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {str(e)}")
    
    def close(self):
        """Close database connection"""
        pass
