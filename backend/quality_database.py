"""
Database Persistence Layer

Stores quality metrics and alerts in SQLite for historical tracking
and retrospective analysis.
"""

import sqlite3
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / 'data' / 'monitoring.db'


class QualityDatabase:
    """SQLite database for quality metrics and alerts"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        Path(self.db_path).parent.mkdir(exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Quality metrics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS quality_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    crypto TEXT NOT NULL,
                    total_records INTEGER,
                    null_count INTEGER,
                    duplicate_count INTEGER,
                    late_arrivals INTEGER,
                    null_rate REAL,
                    duplicate_rate REAL,
                    quality_score REAL,
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (crypto) REFERENCES cryptos(name)
                )
            ''')
            
            # Alerts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id TEXT UNIQUE NOT NULL,
                    crypto TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    metric_value REAL,
                    threshold REAL,
                    message TEXT,
                    triggered_at TIMESTAMP NOT NULL,
                    resolved_at TIMESTAMP,
                    status TEXT DEFAULT 'active',
                    FOREIGN KEY (crypto) REFERENCES cryptos(name)
                )
            ''')
            
            # Cryptocurrencies reference table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cryptos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Thresholds configuration table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS thresholds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric TEXT UNIQUE NOT NULL,
                    value REAL NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indices for faster queries
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_crypto ON alerts(crypto)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_crypto ON quality_metrics(crypto)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON quality_metrics(checked_at)')
            
            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")
    
    def store_metrics(self, metrics_dict: Dict):
        """Store quality metrics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for crypto, metrics in metrics_dict.items():
                    # Ensure crypto exists
                    cursor.execute('INSERT OR IGNORE INTO cryptos (name) VALUES (?)', (crypto,))
                    
                    # Store metrics
                    cursor.execute('''
                        INSERT INTO quality_metrics 
                        (crypto, total_records, null_count, duplicate_count, late_arrivals,
                         null_rate, duplicate_rate, quality_score)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        metrics['crypto'],
                        metrics['total_records'],
                        metrics['null_count'],
                        metrics['duplicate_count'],
                        metrics['late_arrivals'],
                        metrics['null_rate'],
                        metrics['duplicate_rate'],
                        metrics['quality_score']
                    ))
                
                conn.commit()
                logger.debug(f"Stored metrics for {len(metrics_dict)} cryptocurrencies")
        except Exception as e:
            logger.error(f"Error storing metrics: {e}")
    
    def store_alert(self, alert_dict: Dict):
        """Store quality alert"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Ensure crypto exists
                cursor.execute('INSERT OR IGNORE INTO cryptos (name) VALUES (?)', 
                             (alert_dict['crypto'],))
                
                cursor.execute('''
                    INSERT INTO alerts 
                    (alert_id, crypto, alert_type, severity, metric_value, threshold, 
                     message, triggered_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    alert_dict['alert_id'],
                    alert_dict['crypto'],
                    alert_dict['alert_type'],
                    alert_dict['severity'],
                    alert_dict['metric_value'],
                    alert_dict['threshold'],
                    alert_dict['message'],
                    alert_dict['triggered_at'],
                    'active'
                ))
                
                conn.commit()
                logger.info(f"Stored alert {alert_dict['alert_id']}")
        except sqlite3.IntegrityError:
            logger.debug(f"Alert already exists: {alert_dict['alert_id']}")
        except Exception as e:
            logger.error(f"Error storing alert: {e}")
    
    def resolve_alert(self, alert_id: str):
        """Mark alert as resolved"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE alerts 
                    SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP
                    WHERE alert_id = ?
                ''', (alert_id,))
                conn.commit()
                logger.info(f"Resolved alert {alert_id}")
        except Exception as e:
            logger.error(f"Error resolving alert: {e}")
    
    def get_active_alerts(self) -> List[Dict]:
        """Get all active alerts from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM alerts 
                    WHERE status = 'active'
                    ORDER BY triggered_at DESC
                ''')
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error retrieving active alerts: {e}")
            return []
    
    def get_alert_history(self, limit: int = 100) -> List[Dict]:
        """Get alert history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM alerts 
                    ORDER BY triggered_at DESC
                    LIMIT ?
                ''', (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error retrieving alert history: {e}")
            return []
    
    def get_metrics_history(self, crypto: str, hours: int = 24) -> List[Dict]:
        """Get historical metrics for a cryptocurrency"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM quality_metrics 
                    WHERE crypto = ? AND checked_at >= datetime('now', ? || ' hours')
                    ORDER BY checked_at DESC
                ''', (crypto, -hours))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error retrieving metrics history: {e}")
            return []
    
    def store_threshold(self, metric: str, value: float):
        """Store threshold configuration"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO thresholds (metric, value)
                    VALUES (?, ?)
                ''', (metric, value))
                conn.commit()
                logger.info(f"Stored threshold: {metric} = {value}")
        except Exception as e:
            logger.error(f"Error storing threshold: {e}")
    
    def get_thresholds(self) -> Dict[str, float]:
        """Get all thresholds"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT metric, value FROM thresholds')
                return {row[0]: row[1] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error retrieving thresholds: {e}")
            return {}
    
    def get_summary_stats(self) -> Dict:
        """Get summary statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total monitored assets
                cursor.execute('SELECT COUNT(DISTINCT crypto) FROM quality_metrics')
                total_assets = cursor.fetchone()[0]
                
                # Active alerts
                cursor.execute('SELECT COUNT(*) FROM alerts WHERE status = "active"')
                active_alerts = cursor.fetchone()[0]
                
                # Critical alerts
                cursor.execute('SELECT COUNT(*) FROM alerts WHERE status = "active" AND severity = "critical"')
                critical_alerts = cursor.fetchone()[0]
                
                # Average quality score
                cursor.execute('SELECT AVG(quality_score) FROM quality_metrics WHERE checked_at >= datetime("now", "-1 hour")')
                avg_quality = cursor.fetchone()[0] or 0
                
                return {
                    'total_monitored_assets': total_assets,
                    'active_alerts': active_alerts,
                    'critical_alerts': critical_alerts,
                    'average_quality_score': round(avg_quality, 2),
                    'last_updated': datetime.utcnow().isoformat()
                }
        except Exception as e:
            logger.error(f"Error retrieving summary stats: {e}")
            return {}
    
    def cleanup_old_data(self, days: int = 30):
        """Remove metrics older than specified days"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM quality_metrics 
                    WHERE checked_at < datetime('now', ? || ' days')
                ''', (-days,))
                deleted = cursor.rowcount
                conn.commit()
                logger.info(f"Cleaned up {deleted} old metric records")
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
