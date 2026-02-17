"""
Data Quality Monitoring Module

Tracks data quality metrics including:
- Null rates (missing data)
- Duplicate rates (repeated records)
- Late arrivals (stale data)
- Alert generation when thresholds breached
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class QualityAlert:
    """Represents a data quality alert"""
    
    def __init__(self, alert_id: str, crypto: str, alert_type: str, 
                 severity: str, metric_value: float, threshold: float, 
                 message: str, triggered_at: datetime = None):
        self.alert_id = alert_id
        self.crypto = crypto
        self.alert_type = alert_type  # 'null_rate', 'duplicate_rate', 'late_arrival'
        self.severity = severity  # 'warning', 'critical'
        self.metric_value = metric_value
        self.threshold = threshold
        self.message = message
        self.triggered_at = triggered_at or datetime.utcnow()
        self.resolved_at = None
    
    def to_dict(self):
        """Convert alert to dictionary"""
        return {
            'alert_id': self.alert_id,
            'crypto': self.crypto,
            'alert_type': self.alert_type,
            'severity': self.severity,
            'metric_value': round(self.metric_value, 2),
            'threshold': round(self.threshold, 2),
            'message': self.message,
            'triggered_at': self.triggered_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'status': 'resolved' if self.resolved_at else 'active'
        }


class QualityMetrics:
    """Tracks quality metrics for a single cryptocurrency"""
    
    def __init__(self, crypto: str):
        self.crypto = crypto
        self.total_records = 0
        self.null_count = 0  # Missing price, market cap, volume
        self.duplicate_count = 0  # Duplicate records in same batch
        self.late_arrivals = 0  # Data older than 5 minutes
        self.timestamp = datetime.utcnow()
        self.quality_score = 100.0
    
    def calculate_null_rate(self) -> float:
        """Calculate percentage of null/missing fields"""
        if self.total_records == 0:
            return 0.0
        return (self.null_count / self.total_records) * 100
    
    def calculate_duplicate_rate(self) -> float:
        """Calculate percentage of duplicate records"""
        if self.total_records == 0:
            return 0.0
        return (self.duplicate_count / self.total_records) * 100
    
    def update_quality_score(self):
        """Recalculate quality score based on metrics"""
        # Start at 100, deduct for issues
        score = 100.0
        
        # Deduct for null values (up to 30 points)
        null_rate = self.calculate_null_rate()
        score -= min(30, null_rate * 0.3)
        
        # Deduct for duplicates (up to 20 points)
        duplicate_rate = self.calculate_duplicate_rate()
        score -= min(20, duplicate_rate * 0.2)
        
        # Deduct for late arrivals (up to 20 points)
        late_rate = (self.late_arrivals / max(1, self.total_records)) * 100
        score -= min(20, late_rate * 0.2)
        
        self.quality_score = max(0.0, score)
    
    def to_dict(self):
        """Convert metrics to dictionary"""
        return {
            'crypto': self.crypto,
            'total_records': self.total_records,
            'null_count': self.null_count,
            'duplicate_count': self.duplicate_count,
            'late_arrivals': self.late_arrivals,
            'null_rate': round(self.calculate_null_rate(), 2),
            'duplicate_rate': round(self.calculate_duplicate_rate(), 2),
            'quality_score': round(self.quality_score, 2),
            'timestamp': self.timestamp.isoformat()
        }


class QualityMonitor:
    """Monitors data quality and triggers alerts"""
    
    def __init__(self):
        self.thresholds = {
            'null_rate': 10.0,  # Alert if > 10% nulls
            'duplicate_rate': 5.0,  # Alert if > 5% duplicates
            'late_arrival': 5.0,  # Alert if > 5% late arrivals
            'quality_score': 80.0  # Alert if < 80 quality score
        }
        self.metrics: Dict[str, QualityMetrics] = {}
        self.active_alerts: List[QualityAlert] = []
        self.alert_history: List[QualityAlert] = []
        self.alert_counter = 0
    
    def ingest_data(self, crypto_data: Dict, data_timestamp: datetime = None) -> QualityMetrics:
        """
        Process incoming data and track quality metrics
        
        Args:
            crypto_data: Dict with keys like 'bitcoin', 'ethereum', etc.
            data_timestamp: When the data was collected
        
        Returns:
            Updated QualityMetrics
        """
        if data_timestamp is None:
            data_timestamp = datetime.utcnow()
        
        metrics_list = []
        
        for crypto, data in crypto_data.items():
            if crypto not in self.metrics:
                self.metrics[crypto] = QualityMetrics(crypto)
            
            metrics = self.metrics[crypto]
            metrics.total_records += 1
            metrics.timestamp = datetime.utcnow()
            
            # Track null values
            required_fields = ['price', 'market_cap', 'volume_24h']
            for field in required_fields:
                if not data.get(field):
                    metrics.null_count += 1
            
            # Check for late arrivals (data older than 5 minutes)
            age_minutes = (datetime.utcnow() - data_timestamp).total_seconds() / 60
            if age_minutes > 5:
                metrics.late_arrivals += 1
            
            # Calculate quality score
            metrics.update_quality_score()
            
            # Check for alert conditions
            self._check_thresholds(crypto, metrics)
            
            metrics_list.append(metrics)
        
        return metrics_list[-1] if metrics_list else None
    
    def _check_thresholds(self, crypto: str, metrics: QualityMetrics):
        """Check metrics against thresholds and trigger alerts"""
        
        # Check null rate
        null_rate = metrics.calculate_null_rate()
        if null_rate > self.thresholds['null_rate']:
            self._trigger_alert(
                crypto, 'null_rate',
                null_rate,
                self.thresholds['null_rate'],
                f"High null rate: {null_rate:.1f}% (threshold: {self.thresholds['null_rate']}%)"
            )
        
        # Check duplicate rate
        dup_rate = metrics.calculate_duplicate_rate()
        if dup_rate > self.thresholds['duplicate_rate']:
            self._trigger_alert(
                crypto, 'duplicate_rate',
                dup_rate,
                self.thresholds['duplicate_rate'],
                f"High duplicate rate: {dup_rate:.1f}% (threshold: {self.thresholds['duplicate_rate']}%)"
            )
        
        # Check quality score
        if metrics.quality_score < self.thresholds['quality_score']:
            severity = 'critical' if metrics.quality_score < 60 else 'warning'
            self._trigger_alert(
                crypto, 'quality_score',
                metrics.quality_score,
                self.thresholds['quality_score'],
                f"Low data quality score: {metrics.quality_score:.1f} (threshold: {self.thresholds['quality_score']})",
                severity=severity
            )
    
    def _trigger_alert(self, crypto: str, alert_type: str, metric_value: float,
                      threshold: float, message: str, severity: str = 'warning'):
        """Create and log an alert"""
        self.alert_counter += 1
        alert_id = f"ALR-{self.alert_counter:04d}"
        
        # Check if similar alert already active
        for active_alert in self.active_alerts:
            if (active_alert.crypto == crypto and 
                active_alert.alert_type == alert_type and
                active_alert.resolved_at is None):
                logger.warning(f"Alert already active: {alert_id} - {message}")
                return
        
        alert = QualityAlert(
            alert_id=alert_id,
            crypto=crypto,
            alert_type=alert_type,
            severity=severity,
            metric_value=metric_value,
            threshold=threshold,
            message=message
        )
        
        self.active_alerts.append(alert)
        logger.warning(f"[{severity.upper()}] Quality Alert {alert_id}: {message}")
    
    def resolve_alert(self, alert_id: str):
        """Resolve an alert"""
        for alert in self.active_alerts:
            if alert.alert_id == alert_id:
                alert.resolved_at = datetime.utcnow()
                self.alert_history.append(alert)
                self.active_alerts.remove(alert)
                logger.info(f"Alert resolved: {alert_id}")
                return True
        return False
    
    def get_active_alerts(self) -> List[Dict]:
        """Get all active alerts"""
        return [alert.to_dict() for alert in self.active_alerts]
    
    def get_alert_history(self, limit: int = 100) -> List[Dict]:
        """Get alert history"""
        return [alert.to_dict() for alert in self.alert_history[-limit:]]
    
    def get_metrics(self, crypto: Optional[str] = None) -> Dict:
        """Get quality metrics"""
        if crypto:
            if crypto in self.metrics:
                return self.metrics[crypto].to_dict()
            return None
        
        return {
            name: metrics.to_dict()
            for name, metrics in self.metrics.items()
        }
    
    def set_threshold(self, metric: str, value: float):
        """Update alert thresholds"""
        if metric in self.thresholds:
            self.thresholds[metric] = value
            logger.info(f"Updated threshold for {metric}: {value}")
    
    def get_status_summary(self) -> Dict:
        """Get overall quality status summary"""
        total_metrics = len(self.metrics)
        avg_quality = sum(m.quality_score for m in self.metrics.values()) / max(1, total_metrics)
        
        return {
            'total_monitored_assets': total_metrics,
            'active_alerts': len(self.active_alerts),
            'critical_alerts': sum(1 for a in self.active_alerts if a.severity == 'critical'),
            'average_quality_score': round(avg_quality, 2),
            'last_updated': datetime.utcnow().isoformat(),
            'health_status': 'healthy' if len(self.active_alerts) == 0 else 'degraded'
        }
