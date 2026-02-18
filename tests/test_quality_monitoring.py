"""
Unit tests for quality monitoring module

Tests data quality tracking, alert generation, and threshold management.
"""

import pytest
import tempfile
import os
import gc
import time
from datetime import datetime, timedelta
from backend.quality_monitoring import QualityMonitor, QualityAlert, QualityMetrics
from backend.quality_database import QualityDatabase


class TestQualityMonitor:
    """Test suite for QualityMonitor class"""
    
    @pytest.fixture
    def monitor(self):
        """Create a quality monitor instance"""
        return QualityMonitor()
    
    def test_monitor_initialization(self, monitor):
        """Test monitor initializes with correct default thresholds"""
        assert monitor.thresholds['null_rate'] == 10.0
        assert monitor.thresholds['duplicate_rate'] == 5.0
        assert monitor.thresholds['quality_score'] == 80.0
        assert len(monitor.metrics) == 0
        assert len(monitor.active_alerts) == 0
    
    def test_ingest_valid_data(self, monitor):
        """Test ingesting valid cryptocurrency data"""
        data = {
            'bitcoin': {
                'price': 45000,
                'market_cap': 880000000000,
                'volume_24h': 25000000000
            },
            'ethereum': {
                'price': 2500,
                'market_cap': 300000000000,
                'volume_24h': 12000000000
            }
        }
        
        metrics = monitor.ingest_data(data)
        
        assert 'bitcoin' in monitor.metrics
        assert 'ethereum' in monitor.metrics
        assert monitor.metrics['bitcoin'].total_records == 1
        assert monitor.metrics['bitcoin'].quality_score > 0
    
    def test_detect_null_values(self, monitor):
        """Test detection of null/missing values"""
        data = {
            'bitcoin': {
                'price': 45000,
                'market_cap': None,  # Missing
                'volume_24h': 25000000000
            }
        }
        
        monitor.ingest_data(data)
        metrics = monitor.get_metrics('bitcoin')
        
        assert metrics['null_count'] == 1
        assert metrics['null_rate'] > 0
    
    def test_high_null_rate_triggers_alert(self, monitor):
        """Test that high null rate triggers alert"""
        # Ingest data with multiple null values
        for i in range(5):
            data = {
                'bitcoin': {
                    'price': None if i > 2 else 45000,
                    'market_cap': None,
                    'volume_24h': None
                }
            }
            monitor.ingest_data(data)
        
        alerts = monitor.get_active_alerts()
        alert_types = [a['alert_type'] for a in alerts]
        
        assert any(at == 'null_rate' for at in alert_types)
    
    def test_low_quality_score_triggers_alert(self, monitor):
        """Test that low quality score triggers alert"""
        # Ingest data that results in low quality score
        data = {
            'bitcoin': {
                'price': None,
                'market_cap': None,
                'volume_24h': None
            }
        }
        
        monitor.ingest_data(data)
        alerts = monitor.get_active_alerts()
        alert_types = [a['alert_type'] for a in alerts]
        
        assert any(at == 'quality_score' for at in alert_types)
    
    def test_late_arrival_detection(self, monitor):
        """Test detection of stale/late arriving data"""
        # Create data timestamp 10 minutes in the past
        old_timestamp = datetime.utcnow() - timedelta(minutes=10)
        
        data = {
            'bitcoin': {
                'price': 45000,
                'market_cap': 880000000000,
                'volume_24h': 25000000000
            }
        }
        
        monitor.ingest_data(data, old_timestamp)
        metrics = monitor.get_metrics('bitcoin')
        
        assert metrics['late_arrivals'] == 1
    
    def test_quality_score_calculation(self, monitor):
        """Test quality score calculation is correct"""
        # Ingest good data
        good_data = {
            'bitcoin': {
                'price': 45000,
                'market_cap': 880000000000,
                'volume_24h': 25000000000
            }
        }
        monitor.ingest_data(good_data)
        
        metrics = monitor.get_metrics('bitcoin')
        assert metrics['quality_score'] == 100.0
        
        # Ingest bad data
        bad_data = {
            'ethereum': {
                'price': None,
                'market_cap': None,
                'volume_24h': None
            }
        }
        monitor.ingest_data(bad_data)
        
        metrics = monitor.get_metrics('ethereum')
        assert metrics['quality_score'] < 100.0
    
    def test_set_custom_threshold(self, monitor):
        """Test updating alert thresholds"""
        original_threshold = monitor.thresholds['null_rate']
        
        monitor.set_threshold('null_rate', 15.0)
        
        assert monitor.thresholds['null_rate'] == 15.0
        assert monitor.thresholds['null_rate'] != original_threshold
    
    def test_alert_resolution(self, monitor):
        """Test resolving active alerts"""
        # Create an alert
        data = {
            'bitcoin': {
                'price': None,
                'market_cap': None,
                'volume_24h': None
            }
        }
        monitor.ingest_data(data)
        
        alerts = monitor.get_active_alerts()
        assert len(alerts) > 0
        
        # Get all alert IDs and resolve them
        alert_ids = [a['alert_id'] for a in alerts]
        for alert_id in alert_ids:
            monitor.resolve_alert(alert_id)
        
        active = monitor.get_active_alerts()
        assert len(active) == 0
    
    def test_status_summary(self, monitor):
        """Test status summary generation"""
        data = {
            'bitcoin': {
                'price': 45000,
                'market_cap': 880000000000,
                'volume_24h': 25000000000
            }
        }
        monitor.ingest_data(data)
        
        summary = monitor.get_status_summary()
        
        assert 'total_monitored_assets' in summary
        assert 'active_alerts' in summary
        assert 'average_quality_score' in summary
        assert 'health_status' in summary
        assert summary['total_monitored_assets'] == 1
    
    def test_multiple_cryptos_tracking(self, monitor):
        """Test tracking multiple cryptocurrencies"""
        cryptos = ['bitcoin', 'ethereum', 'cardano', 'polkadot']
        data = {
            crypto: {
                'price': 1000 * i,
                'market_cap': 100000000000 * i,
                'volume_24h': 10000000000 * i
            }
            for i, crypto in enumerate(cryptos, 1)
        }
        
        monitor.ingest_data(data)
        
        assert len(monitor.metrics) == 4
        for crypto in cryptos:
            assert crypto in monitor.metrics

    def test_ingest_coingecko_payload_shape(self, monitor):
        """Test ingestion supports raw CoinGecko response keys."""
        data = {
            '_metadata': {
                'timestamp': datetime.utcnow().isoformat(),
                'source': 'CoinGecko'
            },
            'bitcoin': {
                'usd': 45000,
                'usd_market_cap': 880000000000,
                'usd_24h_vol': 25000000000
            }
        }

        monitor.ingest_data(data)
        metrics = monitor.get_metrics('bitcoin')

        assert metrics['total_records'] == 1
        assert metrics['null_count'] == 0
        assert metrics['quality_score'] == 100.0

    def test_ingest_ignores_metadata_records(self, monitor):
        """Test metadata keys are ignored and not tracked as cryptocurrencies."""
        data = {
            '_metadata': {'source': 'CoinGecko'},
            '_system': {'trace_id': 'abc-123'},
            'ethereum': {
                'usd': 2500,
                'usd_market_cap': 300000000000,
                'usd_24h_vol': 12000000000
            }
        }

        monitor.ingest_data(data)
        all_metrics = monitor.get_metrics()

        assert 'ethereum' in all_metrics
        assert '_metadata' not in all_metrics
        assert '_system' not in all_metrics


class TestQualityAlert:
    """Test suite for QualityAlert class"""
    
    def test_alert_creation(self):
        """Test creating a quality alert"""
        alert = QualityAlert(
            alert_id='ALR-0001',
            crypto='bitcoin',
            alert_type='null_rate',
            severity='warning',
            metric_value=12.5,
            threshold=10.0,
            message='High null rate detected'
        )
        
        assert alert.alert_id == 'ALR-0001'
        assert alert.crypto == 'bitcoin'
        assert alert.resolved_at is None
    
    def test_alert_to_dict(self):
        """Test converting alert to dictionary"""
        alert = QualityAlert(
            alert_id='ALR-0001',
            crypto='bitcoin',
            alert_type='null_rate',
            severity='warning',
            metric_value=12.5,
            threshold=10.0,
            message='High null rate'
        )
        
        alert_dict = alert.to_dict()
        
        assert alert_dict['alert_id'] == 'ALR-0001'
        assert alert_dict['status'] == 'active'
        assert 'triggered_at' in alert_dict


class TestQualityDatabase:
    """Test suite for QualityDatabase class"""
    
    @pytest.fixture
    def db(self):
        """Create temporary database for testing"""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, 'test.db')
        database = QualityDatabase(db_path)
        yield database
        # Cleanup - close connection first, then delete
        del database
        gc.collect()
        time.sleep(0.1)  # Give time for connection to close
        try:
            if os.path.exists(db_path):
                os.remove(db_path)
            os.rmdir(temp_dir)
        except Exception:
            pass  # Ignore cleanup errors
    
    def test_database_initialization(self, db):
        """Test database tables are created"""
        assert os.path.exists(db.db_path)
    
    def test_store_metrics(self, db):
        """Test storing metrics in database"""
        metrics_dict = {
            'bitcoin': {
                'crypto': 'bitcoin',
                'total_records': 10,
                'null_count': 1,
                'duplicate_count': 0,
                'late_arrivals': 0,
                'null_rate': 10.0,
                'duplicate_rate': 0.0,
                'quality_score': 90.0
            }
        }
        
        db.store_metrics(metrics_dict)
        
        # Query and verify
        history = db.get_metrics_history('bitcoin', hours=24)
        assert len(history) > 0
    
    def test_store_and_retrieve_alert(self, db):
        """Test storing and retrieving alerts"""
        alert_dict = {
            'alert_id': 'ALR-0001',
            'crypto': 'bitcoin',
            'alert_type': 'null_rate',
            'severity': 'warning',
            'metric_value': 12.5,
            'threshold': 10.0,
            'message': 'High null rate',
            'triggered_at': datetime.utcnow().isoformat()
        }
        
        db.store_alert(alert_dict)
        
        active_alerts = db.get_active_alerts()
        assert len(active_alerts) > 0
    
    def test_resolve_alert_in_database(self, db):
        """Test resolving alert in database"""
        alert_dict = {
            'alert_id': 'ALR-0001',
            'crypto': 'bitcoin',
            'alert_type': 'null_rate',
            'severity': 'warning',
            'metric_value': 12.5,
            'threshold': 10.0,
            'message': 'High null rate',
            'triggered_at': datetime.utcnow().isoformat()
        }
        
        db.store_alert(alert_dict)
        db.resolve_alert('ALR-0001')
        
        active_alerts = db.get_active_alerts()
        assert len(active_alerts) == 0
    
    def test_threshold_management(self, db):
        """Test storing and retrieving thresholds"""
        db.store_threshold('null_rate', 15.0)
        db.store_threshold('duplicate_rate', 8.0)
        
        thresholds = db.get_thresholds()
        
        assert thresholds['null_rate'] == 15.0
        assert thresholds['duplicate_rate'] == 8.0
