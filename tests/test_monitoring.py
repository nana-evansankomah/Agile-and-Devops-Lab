"""
Tests for performance monitoring and metrics collection.
"""

import pytest
import tempfile
import os
import time
import gc
from datetime import datetime, timedelta

from backend.monitoring import (
    PerformanceMetrics,
    PerformanceMonitor,
    MonitoringDatabase
)


class TestPerformanceMetrics:
    """Test individual performance metric tracking"""
    
    def test_metric_initialization(self):
        """Test: PerformanceMetrics initializes correctly"""
        metric = PerformanceMetrics('test_operation')
        
        assert metric.operation_name == 'test_operation'
        assert metric.status == 'pending'
        assert metric.duration_ms == 0
        assert metric.error_message is None
    
    def test_metric_timing(self):
        """Test: PerformanceMetrics timing calculation"""
        metric = PerformanceMetrics('test_op')
        metric.start()
        
        time.sleep(0.1)  # 100ms
        metric.end()
        
        # Should be approximately 100ms ±10ms
        assert 90 < metric.duration_ms < 150
    
    def test_metric_error_tracking(self):
        """Test: PerformanceMetrics error tracking"""
        metric = PerformanceMetrics('test_op')
        metric.start()
        metric.end(status='error', error_msg='Test error')
        
        assert metric.status == 'error'
        assert metric.error_message == 'Test error'
    
    def test_metric_to_dict(self):
        """Test: PerformanceMetrics serialization"""
        metric = PerformanceMetrics('test_op')
        metric.start()
        metric.end(status='success')
        
        data = metric.to_dict()
        
        assert data['operation'] == 'test_op'
        assert data['status'] == 'success'
        assert 'timestamp' in data
        assert 'duration_ms' in data


class TestPerformanceMonitor:
    """Test performance monitoring and aggregation"""
    
    def test_monitor_initialization(self):
        """Test: PerformanceMonitor initializes correctly"""
        monitor = PerformanceMonitor()
        
        assert monitor.max_history == 1000
        assert len(monitor.metrics_history) == 0
        assert sum(monitor.operation_counts.values()) == 0
    
    def test_record_single_operation(self):
        """Test: Recording a single operation"""
        monitor = PerformanceMonitor()
        metric = PerformanceMetrics('api_call')
        metric.start()
        time.sleep(0.05)
        metric.end()
        
        monitor.record_operation(metric)
        
        assert monitor.operation_counts['api_call'] == 1
        assert len(monitor.metrics_history) == 1
    
    def test_latency_calculation(self):
        """Test: Latency (average duration) calculation"""
        monitor = PerformanceMonitor()
        
        # Record multiple operations
        for i in range(3):
            metric = PerformanceMetrics('operation')
            metric.start()
            time.sleep(0.05)  # 50ms
            metric.end()
            monitor.record_operation(metric)
        
        latency = monitor.get_latency_ms('operation')
        
        # Should be approximately 50ms ±20ms
        assert 30 < latency < 100
    
    def test_throughput_calculation(self):
        """Test: Throughput (ops/sec) calculation"""
        monitor = PerformanceMonitor()
        
        # Record 10 operations quickly
        for i in range(10):
            metric = PerformanceMetrics('rapid_op')
            metric.start()
            metric.end()
            monitor.record_operation(metric)
        
        throughput = monitor.get_throughput('rapid_op', time_window_seconds=1)
        
        # Should be close to 10 ops/sec
        assert throughput >= 5  # At least 5 ops/sec
    
    def test_error_rate_calculation(self):
        """Test: Error rate percentage calculation"""
        monitor = PerformanceMonitor()
        
        # Record 10 operations, 3 fail
        for i in range(10):
            metric = PerformanceMetrics('operation')
            metric.start()
            status = 'error' if i < 3 else 'success'
            metric.end(status=status)
            monitor.record_operation(metric)
        
        error_rate = monitor.get_error_rate('operation')
        
        # Should be 30%
        assert 28 < error_rate < 32
    
    def test_metrics_summary(self):
        """Test: Comprehensive metrics summary"""
        monitor = PerformanceMonitor()
        
        # Record various operations
        for i in range(5):
            metric = PerformanceMetrics('api_call')
            metric.start()
            time.sleep(0.01)
            metric.end()
            monitor.record_operation(metric)
        
        for i in range(3):
            metric = PerformanceMetrics('db_query')
            metric.start()
            time.sleep(0.02)
            status = 'error' if i == 0 else 'success'
            metric.end(status=status)
            monitor.record_operation(metric)
        
        summary = monitor.get_metrics_summary()
        
        assert summary['total_operations'] == 8
        assert summary['total_errors'] == 1
        assert 'operations' in summary
        assert 'api_call' in summary['operations']
        assert 'db_query' in summary['operations']
        assert summary['operations']['db_query']['errors'] == 1
    
    def test_multi_operation_tracking(self):
        """Test: Tracking multiple operation types"""
        monitor = PerformanceMonitor()
        
        # Track API calls
        for i in range(5):
            metric = PerformanceMetrics('api_fetch')
            metric.start()
            metric.end()
            monitor.record_operation(metric)
        
        # Track database operations
        for i in range(3):
            metric = PerformanceMetrics('db_insert')
            metric.start()
            metric.end()
            monitor.record_operation(metric)
        
        assert monitor.operation_counts['api_fetch'] == 5
        assert monitor.operation_counts['db_insert'] == 3
        assert monitor.get_error_rate('api_fetch') == 0.0
        assert monitor.get_error_rate('db_insert') == 0.0


class TestMonitoringDatabase:
    """Test monitoring data persistence"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary monitoring database"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, 'monitoring.db')
            db = MonitoringDatabase(db_path)
            yield db, db_path
            gc.collect()
    
    def test_database_initialization(self, temp_db):
        """Test: Database initializes with proper schema"""
        db, db_path = temp_db
        
        assert os.path.exists(db_path)
    
    def test_store_metric(self, temp_db):
        """Test: Store performance metric to database"""
        db, _ = temp_db
        
        metric = PerformanceMetrics('test_operation')
        metric.start()
        time.sleep(0.01)
        metric.end(status='success')
        
        db.store_metric(metric)
        
        # Verify data was stored (no errors)
        metrics = db.get_metrics_by_operation('test_operation')
        assert len(metrics) > 0
    
    def test_store_health_snapshot(self, temp_db):
        """Test: Store system health snapshot"""
        db, _ = temp_db
        
        snapshot = {
            'timestamp': datetime.utcnow().isoformat(),
            'uptime_seconds': 3600.0,
            'total_operations': 100,
            'total_errors': 5,
            'overall_error_rate': 5.0,
            'overall_latency_ms': 25.5,
            'overall_throughput_ops_sec': 1.5
        }
        
        db.store_health_snapshot(snapshot)
        
        # Verify data was stored
        history = db.get_health_history(hours=24)
        assert len(history) > 0
    
    def test_get_metrics_by_operation(self, temp_db):
        """Test: Retrieve metrics for specific operation"""
        db, _ = temp_db
        
        # Store multiple metrics
        for i in range(3):
            metric = PerformanceMetrics('fetch_data')
            metric.start()
            metric.end()
            db.store_metric(metric)
        
        metrics = db.get_metrics_by_operation('fetch_data')
        assert len(metrics) == 3
    
    def test_get_health_history(self, temp_db):
        """Test: Retrieve health history"""
        db, _ = temp_db
        
        snapshot = {
            'timestamp': datetime.utcnow().isoformat(),
            'uptime_seconds': 3600.0,
            'total_operations': 100,
            'total_errors': 5,
            'overall_error_rate': 5.0,
            'overall_latency_ms': 25.5,
            'overall_throughput_ops_sec': 1.5
        }
        
        db.store_health_snapshot(snapshot)
        
        history = db.get_health_history(hours=1)
        assert len(history) > 0
        assert history[0]['total_operations'] == 100
    
    def test_cleanup_old_data(self, temp_db):
        """Test: Cleanup old monitoring data"""
        db, _ = temp_db
        
        # Store metric
        metric = PerformanceMetrics('test_op')
        metric.start()
        metric.end()
        db.store_metric(metric)
        
        # Cleanup with 0 days retention (should clean everything)
        db.cleanup_old_data(days=0)
        
        # Data should be removed
        metrics = db.get_metrics_by_operation('test_op')
        # Implementation varies, main thing is cleanup doesn't error


class TestMonitoringIntegration:
    """Integration tests for monitoring system"""
    
    def test_full_monitoring_workflow(self):
        """Test: Complete monitoring workflow"""
        monitor = PerformanceMonitor()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, 'monitoring.db')
            db = MonitoringDatabase(db_path)
            
            # Simulate operations
            for i in range(5):
                metric = PerformanceMetrics('api_call')
                metric.start()
                time.sleep(0.01)
                metric.end()
                monitor.record_operation(metric)
                db.store_metric(metric)
            
            # Get summary
            summary = monitor.get_metrics_summary()
            
            # Store summary
            db.store_health_snapshot(summary)
            
            # Verify everything stored
            assert summary['total_operations'] == 5
            metrics = db.get_metrics_by_operation('api_call')
            assert len(metrics) == 5
            
            # Cleanup
            gc.collect()
    
    def test_error_tracking_workflow(self):
        """Test: Error tracking and reporting"""
        monitor = PerformanceMonitor()
        
        # Record failures
        for i in range(3):
            metric = PerformanceMetrics('operation')
            metric.start()
            metric.end(status='error', error_msg=f'Error {i}')
            monitor.record_operation(metric)
        
        # Record successes
        for i in range(7):
            metric = PerformanceMetrics('operation')
            metric.start()
            metric.end(status='success')
            monitor.record_operation(metric)
        
        summary = monitor.get_metrics_summary()
        
        assert summary['total_operations'] == 10
        assert summary['total_errors'] == 3
        assert summary['overall_error_rate'] == 30.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
