"""Flask application for real-time data streaming dashboard."""
import logging
import os
from flask import Flask, render_template, jsonify, request
from datetime import datetime, timedelta
from backend.config import current_config
from backend.data_ingestion import CoinGeckoIngester
from backend.transformations import DataTransformer
from backend.quality_monitoring import QualityMonitor
from backend.quality_database import QualityDatabase
from backend.monitoring import PerformanceMonitor, MonitoringDatabase, PerformanceMetrics

# Setup logging
os.makedirs('./logs', exist_ok=True)
logging.basicConfig(
    level=current_config.LOG_LEVEL,
    format=current_config.LOG_FORMAT,
    handlers=[
        logging.FileHandler(current_config.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Determine the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_folder = os.path.join(project_root, 'frontend')
static_folder = os.path.join(project_root, 'frontend')

# Initialize Flask app with absolute paths
app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
app.config.from_object(current_config)

# Initialize components
ingester = CoinGeckoIngester(current_config.COINGECKO_API_URL, current_config.CRYPTOS)
transformer = DataTransformer(current_config)
quality_monitor = QualityMonitor()
quality_db = QualityDatabase()

# Initialize monitoring components
performance_monitor = PerformanceMonitor()
monitoring_db = MonitoringDatabase()

# In-memory cache for latest data
cache = {
    'latest_data': None,
    'last_update': None,
    'update_count': 0,
    'error_count': 0,
    'cache_expiry': None  # Timestamp when cache expires
}

# Cache TTL in seconds (60 seconds minimum to respect API rate limits)
CACHE_TTL = 60


@app.route('/')
def index():
    """Serve the dashboard homepage."""
    return render_template('index.html')


@app.route('/api/data')
def get_data():
    """API endpoint to get latest data."""
    return jsonify({
        'data': cache['latest_data'],
        'last_update': cache['last_update'],
        'stats': {
            'update_count': cache['update_count'],
            'error_count': cache['error_count']
        }
    })


@app.route('/api/refresh')
def refresh_data():
    """API endpoint to manually refresh data."""
    # Start performance tracking
    metric = PerformanceMetrics('api_refresh')
    metric.start()
    
    try:
        # Check if cache is still valid
        if cache['cache_expiry'] and datetime.utcnow() < cache['cache_expiry']:
            logger.info("Returning cached data (cache not yet expired)")
            metric.end(status='success')
            performance_monitor.record_operation(metric)
            monitoring_db.store_metric(metric)
            return jsonify({
                'status': 'success',
                'message': 'Returning cached data (API rate limit protection)',
                'data': cache['latest_data']
            }), 200
        
        # Fetch raw data
        raw_data = ingester.fetch_market_data()
        
        if raw_data:
            # Transform data
            transformed_data = transformer.transform_market_data(raw_data)
            
            # Monitor data quality
            quality_monitor.ingest_data(raw_data)
            
            # Store quality metrics
            metrics = quality_monitor.get_metrics()
            quality_db.store_metrics(metrics)
            
            # Store any new alerts
            for alert in quality_monitor.get_active_alerts():
                quality_db.store_alert(alert)
            
            # Update cache with expiry time
            cache['latest_data'] = transformed_data
            cache['last_update'] = datetime.utcnow().isoformat()
            cache['cache_expiry'] = datetime.utcnow() + timedelta(seconds=CACHE_TTL)
            cache['update_count'] += 1
            
            logger.info(f"Data refreshed successfully. Valid records: {transformed_data['summary']['valid_count']}")
            
            # Record successful operation
            metric.end(status='success')
            performance_monitor.record_operation(metric)
            monitoring_db.store_metric(metric)
            
            return jsonify({
                'status': 'success',
                'message': f"Fetched {transformed_data['summary']['valid_count']} cryptocurrencies",
                'data': transformed_data
            }), 200
        else:
            cache['error_count'] += 1
            logger.error("Failed to fetch market data")
            metric.end(status='error', error_msg='Failed to fetch market data from CoinGecko')
            performance_monitor.record_operation(metric)
            monitoring_db.store_metric(metric)
            return jsonify({
                'status': 'error',
                'message': 'Failed to fetch market data from CoinGecko'
            }), 500
            
    except Exception as e:
        cache['error_count'] += 1
        logger.error(f"Error in refresh_data: {str(e)}")
        metric.end(status='error', error_msg=str(e))
        performance_monitor.record_operation(metric)
        monitoring_db.store_metric(metric)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/health')
def health_check():
    """Health check endpoint with monitoring data."""
    ingester_status = ingester.get_status()
    quality_status = quality_monitor.get_status_summary()
    monitoring_summary = performance_monitor.get_metrics_summary()
    
    # Determine overall health status
    overall_error_rate = monitoring_summary.get('overall_error_rate', 0)
    health_status = 'healthy' if overall_error_rate < 10 else ('degraded' if overall_error_rate < 25 else 'unhealthy')
    
    return jsonify({
        'status': health_status,
        'timestamp': datetime.utcnow().isoformat(),
        'ingester': ingester_status,
        'quality': quality_status,
        'monitoring': {
            'error_rate': monitoring_summary.get('overall_error_rate', 0),
            'latency_ms': monitoring_summary.get('overall_latency_ms', 0),
            'throughput_ops_sec': monitoring_summary.get('overall_throughput_ops_sec', 0),
            'total_operations': monitoring_summary.get('total_operations', 0),
            'total_errors': monitoring_summary.get('total_errors', 0)
        },
        'cache': {
            'has_data': cache['latest_data'] is not None,
            'last_update': cache['last_update'],
            'update_count': cache['update_count'],
            'error_count': cache['error_count']
        }
    }), 200


@app.route('/api/quality/metrics')
def get_quality_metrics():
    """Get current quality metrics for all cryptocurrencies."""
    crypto = request.args.get('crypto')
    metrics = quality_monitor.get_metrics(crypto)
    return jsonify({
        'metrics': metrics,
        'timestamp': datetime.utcnow().isoformat()
    }), 200


@app.route('/api/quality/alerts')
def get_quality_alerts():
    """Get active quality alerts."""
    alerts_type = request.args.get('type', 'active')  # 'active', 'history'
    
    if alerts_type == 'history':
        limit = request.args.get('limit', 100, type=int)
        alerts = quality_db.get_alert_history(limit)
    else:
        alerts = quality_db.get_active_alerts()
    
    return jsonify({
        'alerts': alerts,
        'count': len(alerts),
        'timestamp': datetime.utcnow().isoformat()
    }), 200


@app.route('/api/quality/alerts/<alert_id>', methods=['POST'])
def resolve_quality_alert(alert_id):
    """Resolve a quality alert."""
    try:
        quality_db.resolve_alert(alert_id)
        quality_monitor.resolve_alert(alert_id)
        return jsonify({
            'status': 'success',
            'message': f'Alert {alert_id} resolved'
        }), 200
    except Exception as e:
        logger.error(f"Error resolving alert: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/quality/thresholds', methods=['GET', 'POST'])
def manage_thresholds():
    """Get or update quality thresholds."""
    if request.method == 'GET':
        thresholds = quality_monitor.thresholds
        return jsonify({
            'thresholds': thresholds,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            metric = data.get('metric')
            value = data.get('value')
            
            if not metric or value is None:
                return jsonify({
                    'status': 'error',
                    'message': 'metric and value required'
                }), 400
            
            quality_monitor.set_threshold(metric, value)
            quality_db.store_threshold(metric, value)
            
            return jsonify({
                'status': 'success',
                'message': f'Threshold updated: {metric} = {value}'
            }), 200
        except Exception as e:
            logger.error(f"Error updating threshold: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500


@app.route('/api/quality/summary')
def get_quality_summary():
    """Get quality monitoring summary."""
    db_summary = quality_db.get_summary_stats()
    monitor_summary = quality_monitor.get_status_summary()
    
    # Merge summaries
    summary = {**db_summary, **monitor_summary}
    
    return jsonify({
        'summary': summary,
        'timestamp': datetime.utcnow().isoformat()
    }), 200


@app.route('/api/monitoring/metrics')
def get_monitoring_metrics():
    """API endpoint to get performance monitoring metrics."""
    operation = request.args.get('operation')
    
    if operation:
        # Get metrics for specific operation
        all_metrics = performance_monitor.get_metrics_summary()
        operation_metrics = all_metrics.get('operations', {}).get(operation)
        
        if operation_metrics:
            return jsonify({
                'operation': operation,
                'metrics': operation_metrics,
                'timestamp': datetime.utcnow().isoformat()
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': f'No metrics found for operation: {operation}'
            }), 404
    else:
        # Return overall metrics
        metrics = performance_monitor.get_metrics_summary()
        return jsonify({
            'metrics': metrics,
            'timestamp': datetime.utcnow().isoformat()
        }), 200


@app.route('/api/monitoring/health')
def get_monitoring_health():
    """API endpoint to get system health with monitoring data."""
    summary = performance_monitor.get_metrics_summary()
    
    # Determine health status based on error rate
    error_rate = summary.get('overall_error_rate', 0)
    if error_rate < 5:
        health_status = 'excellent'
    elif error_rate < 10:
        health_status = 'healthy'
    elif error_rate < 25:
        health_status = 'degraded'
    else:
        health_status = 'unhealthy'
    
    return jsonify({
        'status': health_status,
        'monitoring': summary,
        'timestamp': datetime.utcnow().isoformat()
    }), 200


@app.route('/api/monitoring/operations')
def get_monitoring_operations():
    """API endpoint to get metrics for all tracked operations."""
    metrics = performance_monitor.get_metrics_summary()
    operations = metrics.get('operations', {})
    
    return jsonify({
        'operations': operations,
        'operation_count': len(operations),
        'timestamp': datetime.utcnow().isoformat()
    }), 200


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500

