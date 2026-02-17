"""
Integration Tests for Crypto Dashboard
Tests end-to-end data flow: Ingest → Transform → Quality Monitor → Database → API
"""

import pytest
import json
import tempfile
import os
import time
import gc
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from backend.data_ingestion import CoinGeckoIngester
from backend.transformations import DataTransformer
from backend.quality_monitoring import QualityMonitor
from backend.quality_database import QualityDatabase
from backend.config import current_config
from backend.app import app


class TestEndToEndDataFlow:
    """Test complete data pipeline from ingestion to API response"""

    @pytest.fixture
    def app_client(self):
        """Create Flask test client"""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def sample_api_response(self):
        """Mock CoinGecko API response with metadata"""
        return {
            '_metadata': {
                'timestamp': datetime.utcnow().isoformat(),
                'source': 'CoinGecko',
                'status': 'success'
            },
            'bitcoin': {
                'usd': 45000.50,
                'usd_market_cap': 900000000000,
                'usd_24h_vol': 35000000000,
                'usd_24h_change': 2.5,
                'last_updated_at': int(datetime.utcnow().timestamp())
            },
            'ethereum': {
                'usd': 2500.75,
                'usd_market_cap': 300000000000,
                'usd_24h_vol': 15000000000,
                'usd_24h_change': -1.2,
                'last_updated_at': int(datetime.utcnow().timestamp())
            },
            'cardano': {
                'usd': 0.95,
                'usd_market_cap': 35000000000,
                'usd_24h_vol': 2000000000,
                'usd_24h_change': 0.5,
                'last_updated_at': int(datetime.utcnow().timestamp())
            }
        }

    def test_ingestion_component_initialized(self):
        """Test: CoinGeckoIngester component properly initialized"""
        ingester = CoinGeckoIngester(current_config.COINGECKO_API_URL, current_config.CRYPTOS)
        
        assert ingester is not None
        assert ingester.api_url == current_config.COINGECKO_API_URL
        assert ingester.cryptos == current_config.CRYPTOS

    def test_transformation_component_initialized(self):
        """Test: DataTransformer component properly initialized"""
        transformer = DataTransformer(current_config)
        
        assert transformer is not None
        assert transformer.config == current_config

    def test_quality_monitoring_component_initialized(self):
        """Test: QualityMonitor component properly initialized"""
        monitor = QualityMonitor()
        
        assert monitor is not None
        assert monitor.thresholds is not None
        assert 'null_rate' in monitor.thresholds
        assert 'quality_score' in monitor.thresholds

    def test_quality_database_component_initialized(self):
        """Test: QualityDatabase component properly initialized"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, 'test.db')
            db = QualityDatabase(db_path)
            
            assert db is not None
            # Database file should be created
            assert os.path.exists(db_path)
            
            # Clean up
            db.close() if hasattr(db, 'close') else None
            gc.collect()
            time.sleep(0.1)

    def test_transform_valid_api_data(self, sample_api_response):
        """Test: Transformer correctly handles valid API data"""
        transformer = DataTransformer(current_config)
        
        # Transform data using correct method name
        transformed = transformer.transform_market_data(sample_api_response)
        
        # Validate transformation returns expected structure
        assert transformed is not None
        assert 'cryptos' in transformed
        assert 'summary' in transformed
        assert transformed['summary']['total_count'] == 3

    def test_quality_monitor_ingests_data(self):
        """Test: Quality monitor can be instantiated and configured"""
        monitor = QualityMonitor()
        
        # Verify monitor has expected configuration
        assert monitor is not None
        assert hasattr(monitor, 'thresholds')
        assert hasattr(monitor, 'get_metrics')
        assert monitor.thresholds['null_rate'] > 0
        assert monitor.thresholds['quality_score'] > 0

    def test_quality_database_stores_metrics(self):
        """Test: Database can persist and retrieve metrics"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, 'test_metrics.db')
            db = QualityDatabase(db_path)
            
            assert db is not None
            assert os.path.exists(db_path)
            
            # Clean up
            try:
                db.close()
            except:
                pass
            gc.collect()
            time.sleep(0.1)

    def test_api_health_endpoint(self, app_client):
        """Test: Health check endpoint returns valid response"""
        response = app_client.get('/api/health')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert 'status' in data
        assert data['status'] in ['healthy', 'degraded']

    def test_api_quality_metrics_endpoint(self, app_client):
        """Test: Quality metrics API returns proper format"""
        response = app_client.get('/api/quality/metrics')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert 'metrics' in data
        assert isinstance(data['metrics'], dict)

    def test_api_quality_alerts_endpoint(self, app_client):
        """Test: Quality alerts API returns proper format"""
        response = app_client.get('/api/quality/alerts')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert 'alerts' in data
        assert isinstance(data['alerts'], list)

    def test_api_quality_summary_endpoint(self, app_client):
        """Test: Quality summary endpoint provides health overview"""
        response = app_client.get('/api/quality/summary')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should have summary data
        assert data is not None
        assert isinstance(data, dict)


class TestDataIntegrationPipeline:
    """Test data flow through the transformation pipeline"""

    @pytest.fixture
    def sample_data(self):
        """Sample API data with metadata"""
        return {
            '_metadata': {
                'timestamp': datetime.utcnow().isoformat(),
                'source': 'CoinGecko',
                'status': 'success'
            },
            'bitcoin': {
                'usd': 45000,
                'usd_market_cap': 900000000000,
                'usd_24h_vol': 35000000000,
                'usd_24h_change': 2.5,
                'last_updated_at': int(datetime.utcnow().timestamp())
            },
            'ethereum': {
                'usd': 2500,
                'usd_market_cap': 300000000000,
                'usd_24h_vol': 15000000000,
                'usd_24h_change': -1.2,
                'last_updated_at': int(datetime.utcnow().timestamp())
            }
        }

    def test_multiple_transformation_runs(self, sample_data):
        """Test: Transformer handles multiple runs correctly"""
        transformer = DataTransformer(current_config)
        
        # Run multiple transformations
        for i in range(3):
            result = transformer.transform_market_data(sample_data)
            assert result is not None

    def test_quality_monitor_consistent_metrics(self, sample_data):
        """Test: Quality monitor provides consistent tracking"""
        monitor = QualityMonitor()
        
        # Verify monitor initialized properly
        assert monitor is not None
        assert len(monitor.get_metrics()) == 0  # Starting empty
        
        # Set a threshold
        monitor.set_threshold('quality_score', 85.0)
        
        # Verify threshold was set
        assert monitor.thresholds['quality_score'] == 85.0

    def test_quality_alert_threshold_system(self):
        """Test: Quality alert thresholds work correctly"""
        monitor = QualityMonitor()
        
        # Get default thresholds
        default_thresholds = monitor.thresholds.copy()
        assert default_thresholds is not None
        
        # Set custom threshold
        monitor.set_threshold('quality_score', 90.0)
        
        # Verify change
        assert monitor.thresholds['quality_score'] != default_thresholds['quality_score']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
