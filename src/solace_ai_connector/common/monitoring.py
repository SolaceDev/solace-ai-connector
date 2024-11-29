from typing import Any
from datadog import initialize, statsd

from .log import log


class Monitoring:
    """
    A singleton class to collect and send metrics to Datadog.
    """

    _instance = None
    _initialized = False
    _ready = False
    _live = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Monitoring, cls).__new__(cls)
        return cls._instance

    def __init__(self, config: dict[str, Any] = None) -> None:
        """
        Initialize the MetricCollector with Datadog configuration.

        :param config: Configuration for Datadog
        """

        if self._initialized:
            return

        self.enabled = False

        monitoring = config.get("monitoring", {})
        if monitoring is not {}:
            self.enabled = monitoring.get("enabled", False)
            tags = monitoring.get("tags", [])
            if "host" not in monitoring:
                log.error(
                    "Monitoring configuration is missing host. Disabling monitoring."
                )
                self.enabled = False
            else:
                host = monitoring.get("host")
            if "port" not in monitoring:
                log.error(
                    "Monitoring configuration is missing port. Disabling monitoring."
                )
                self.enabled = False
            else:
                port = monitoring.get("port")

        # Initialize Datadog with provided options
        if self.enabled:
            options = {
                "statsd_constant_tags": tags,
                "statsd_host": host,
                "statsd_port": port,
            }

            initialize(**options)
        self._initialized = True

    def set_readiness(self, ready: bool) -> None:
        """
        Set the readiness status of the MetricCollector.

        :param ready: Readiness status
        """
        self._ready = ready

    def set_liveness(self, live: bool) -> None:
        """
        Set the liveness status of the MetricCollector.

        :param live: Liveness status
        """
        self._live = live

    def send_metric(self, metric_name: str, metric_value: Any) -> None:
        """
        Send a metric to Datadog.

        :param metric_name: Name of the metric
        :param metric_value: Value of the metric
        """
        if self.enabled:
            statsd.gauge(metric_name, metric_value)
