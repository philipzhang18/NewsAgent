"""
Monitoring and alerting system for service health and performance metrics.
"""

import logging
import time
import psutil
import os
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timezone, timedelta
from collections import deque
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Represents a system alert."""
    severity: AlertSeverity
    message: str
    component: str
    timestamp: datetime
    details: Optional[Dict] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        data = asdict(self)
        data['severity'] = self.severity.value
        data['timestamp'] = self.timestamp.isoformat()
        if self.resolved_at:
            data['resolved_at'] = self.resolved_at.isoformat()
        return data


class HealthChecker:
    """System health checker."""

    def __init__(self):
        """Initialize health checker."""
        self.checks: Dict[str, Callable] = {}
        self.last_check_results: Dict[str, Dict] = {}

    def register_check(self, name: str, check_func: Callable):
        """
        Register a health check function.

        Args:
            name: Name of the health check
            check_func: Function that returns (is_healthy, message, details)
        """
        self.checks[name] = check_func
        logger.info(f"Registered health check: {name}")

    async def run_checks(self) -> Dict[str, Any]:
        """
        Run all registered health checks.

        Returns:
            Dictionary with check results
        """
        results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'healthy': True,
            'checks': {}
        }

        for name, check_func in self.checks.items():
            try:
                is_healthy, message, details = await check_func()

                results['checks'][name] = {
                    'healthy': is_healthy,
                    'message': message,
                    'details': details
                }

                if not is_healthy:
                    results['healthy'] = False

                self.last_check_results[name] = results['checks'][name]

            except Exception as e:
                logger.error(f"Health check '{name}' failed: {str(e)}")
                results['checks'][name] = {
                    'healthy': False,
                    'message': f"Check failed: {str(e)}",
                    'details': {}
                }
                results['healthy'] = False

        return results

    def get_last_results(self) -> Dict:
        """Get results from last health check run."""
        return self.last_check_results


class MetricsCollector:
    """Collect and store system metrics."""

    def __init__(self, max_history: int = 1000):
        """
        Initialize metrics collector.

        Args:
            max_history: Maximum number of metric points to store
        """
        self.max_history = max_history
        self.metrics: Dict[str, deque] = {}
        self.start_time = time.time()

    def record_metric(self, name: str, value: float, timestamp: Optional[datetime] = None):
        """
        Record a metric value.

        Args:
            name: Metric name
            value: Metric value
            timestamp: Optional timestamp (defaults to now)
        """
        if name not in self.metrics:
            self.metrics[name] = deque(maxlen=self.max_history)

        ts = timestamp or datetime.now(timezone.utc)
        self.metrics[name].append((ts, value))

    def get_metric_history(self, name: str, limit: int = 100) -> List[tuple]:
        """Get historical values for a metric."""
        if name not in self.metrics:
            return []

        return list(self.metrics[name])[-limit:]

    def get_metric_stats(self, name: str) -> Dict:
        """Get statistics for a metric."""
        if name not in self.metrics or not self.metrics[name]:
            return {}

        values = [v for _, v in self.metrics[name]]

        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'latest': values[-1] if values else None
        }

    def get_system_metrics(self) -> Dict:
        """Get current system metrics."""
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'process': {
                'cpu_percent': psutil.Process(os.getpid()).cpu_percent(),
                'memory_mb': psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024,
                'threads': psutil.Process(os.getpid()).num_threads()
            },
            'uptime_seconds': time.time() - self.start_time
        }

    def get_all_metrics(self) -> Dict:
        """Get all collected metrics with stats."""
        return {
            name: self.get_metric_stats(name)
            for name in self.metrics.keys()
        }


class AlertManager:
    """Manage system alerts."""

    def __init__(self, max_alerts: int = 500):
        """
        Initialize alert manager.

        Args:
            max_alerts: Maximum number of alerts to store
        """
        self.max_alerts = max_alerts
        self.alerts: deque = deque(maxlen=max_alerts)
        self.alert_handlers: List[Callable] = []

    def register_handler(self, handler: Callable):
        """
        Register an alert handler function.

        Args:
            handler: Function that accepts an Alert object
        """
        self.alert_handlers.append(handler)
        logger.info(f"Registered alert handler: {handler.__name__}")

    async def create_alert(
        self,
        severity: AlertSeverity,
        message: str,
        component: str,
        details: Optional[Dict] = None
    ) -> Alert:
        """
        Create and store an alert.

        Args:
            severity: Alert severity level
            message: Alert message
            component: Component that generated the alert
            details: Additional alert details

        Returns:
            Created Alert object
        """
        alert = Alert(
            severity=severity,
            message=message,
            component=component,
            timestamp=datetime.now(timezone.utc),
            details=details
        )

        self.alerts.append(alert)
        logger.log(
            logging.ERROR if severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL] else logging.WARNING,
            f"Alert: [{component}] {message}"
        )

        # Call alert handlers
        for handler in self.alert_handlers:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {str(e)}")

        return alert

    def get_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        component: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 100
    ) -> List[Alert]:
        """Get alerts with optional filtering."""
        alerts = list(self.alerts)

        # Apply filters
        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        if component:
            alerts = [a for a in alerts if a.component == component]

        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]

        # Sort by timestamp (newest first) and limit
        alerts.sort(key=lambda a: a.timestamp, reverse=True)
        return alerts[:limit]

    def resolve_alert(self, alert: Alert):
        """Mark an alert as resolved."""
        alert.resolved = True
        alert.resolved_at = datetime.now(timezone.utc)
        logger.info(f"Alert resolved: [{alert.component}] {alert.message}")

    def get_alert_summary(self) -> Dict:
        """Get summary of alerts."""
        alerts = list(self.alerts)
        unresolved = [a for a in alerts if not a.resolved]

        return {
            'total': len(alerts),
            'unresolved': len(unresolved),
            'by_severity': {
                'critical': len([a for a in unresolved if a.severity == AlertSeverity.CRITICAL]),
                'error': len([a for a in unresolved if a.severity == AlertSeverity.ERROR]),
                'warning': len([a for a in unresolved if a.severity == AlertSeverity.WARNING]),
                'info': len([a for a in unresolved if a.severity == AlertSeverity.INFO])
            },
            'by_component': self._count_by_component(unresolved)
        }

    def _count_by_component(self, alerts: List[Alert]) -> Dict[str, int]:
        """Count alerts by component."""
        counts = {}
        for alert in alerts:
            counts[alert.component] = counts.get(alert.component, 0) + 1
        return counts


class MonitoringService:
    """Main monitoring service coordinator."""

    def __init__(self):
        """Initialize monitoring service."""
        self.health_checker = HealthChecker()
        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager()

        self.is_running = False
        self.check_interval = 60  # seconds

        # Register default health checks
        self._register_default_checks()

        logger.info("Monitoring service initialized")

    def _register_default_checks(self):
        """Register default system health checks."""
        # CPU check
        async def check_cpu():
            cpu_percent = psutil.cpu_percent(interval=1)
            is_healthy = cpu_percent < 90
            message = f"CPU usage: {cpu_percent}%"
            return is_healthy, message, {'cpu_percent': cpu_percent}

        self.health_checker.register_check('cpu', check_cpu)

        # Memory check
        async def check_memory():
            memory = psutil.virtual_memory()
            is_healthy = memory.percent < 90
            message = f"Memory usage: {memory.percent}%"
            return is_healthy, message, {'memory_percent': memory.percent}

        self.health_checker.register_check('memory', check_memory)

        # Disk check
        async def check_disk():
            disk = psutil.disk_usage('/')
            is_healthy = disk.percent < 90
            message = f"Disk usage: {disk.percent}%"
            return is_healthy, message, {'disk_percent': disk.percent}

        self.health_checker.register_check('disk', check_disk)

    async def start(self):
        """Start monitoring service."""
        self.is_running = True
        logger.info("Monitoring service started")

        # Could start a background task here for periodic checks
        # For now, checks are run on-demand

    async def stop(self):
        """Stop monitoring service."""
        self.is_running = False
        logger.info("Monitoring service stopped")

    async def collect_metrics(self):
        """Collect current system metrics."""
        system_metrics = self.metrics_collector.get_system_metrics()

        # Record key metrics
        self.metrics_collector.record_metric('cpu_percent', system_metrics['cpu_percent'])
        self.metrics_collector.record_metric('memory_percent', system_metrics['memory_percent'])
        self.metrics_collector.record_metric('disk_percent', system_metrics['disk_percent'])
        self.metrics_collector.record_metric('process_memory_mb', system_metrics['process']['memory_mb'])

        return system_metrics

    async def run_health_checks(self) -> Dict:
        """Run all health checks."""
        results = await self.health_checker.run_checks()

        # Create alerts for failed checks
        for check_name, check_result in results['checks'].items():
            if not check_result['healthy']:
                await self.alert_manager.create_alert(
                    severity=AlertSeverity.ERROR,
                    message=check_result['message'],
                    component=f"health_check_{check_name}",
                    details=check_result['details']
                )

        return results

    def get_status(self) -> Dict:
        """Get complete monitoring status."""
        return {
            'monitoring': {
                'running': self.is_running,
                'check_interval': self.check_interval
            },
            'health': self.health_checker.get_last_results(),
            'metrics': {
                'system': self.metrics_collector.get_system_metrics(),
                'collected': self.metrics_collector.get_all_metrics()
            },
            'alerts': self.alert_manager.get_alert_summary()
        }


# Global monitoring service instance
monitoring_service = MonitoringService()
