from typing import Any, List
from enum import Enum


class Metrics(Enum):
    SOLCLIENT_STATS_RX_ACKED = 0


class Monitoring:
    """
    A singleton class to collect and send metrics.
    """

    _instance = None
    _initialized = False
    _ready = False
    _live = False
    _interval = 60

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

        self._initialized = True
        self._collected_metrics = {}

    def set_required_metrics(self, required_metrics: List[Metrics]) -> None:
        """
        Set the required metrics for the MetricCollector.

        :param required_metrics: List of required metrics
        """
        self._required_metrics = required_metrics

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

    def set_interval(self, interval: int) -> None:
        """
        Set the interval for the MetricCollector.

        :param interval: Interval
        """
        self._interval = interval

    def get_interval(self) -> int:
        """
        Get the interval for the MetricCollector.

        :return: Interval
        """
        return self._interval

    def collect_metrics(self, metrics: dict[Metrics, dict[str, Any]]) -> None:
        """
        Collect metrics.

        :param metrics: Dictionary of metrics
        """
        for key, value in metrics.items():
            self._collected_metrics[key.value] = value

    def get_collected_metrics(self) -> List[dict[str, Any]]:
        """
        Retrieve collected metrics.

        :return: Dictionary of collected metrics
        """
        return self._collected_metrics
