from typing import Any, List
from enum import Enum
from threading import Lock


class Metrics(Enum):
    SOLCLIENT_STATS_RX_ACKED = "SOLCLIENT_STATS_RX_ACKED"


class Monitoring:
    """
    A singleton class to collect and send metrics.
    """

    _instance = None
    _initialized = False
    _ready = False
    _live = False
    _interval = 3

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
        self._lock = Lock()
        self._initialize_metrics()

    def _initialize_metrics(self) -> None:
        """
        Initialize the MetricCollector.
        """
        self._required_metrics = [metric.value for metric in Metrics]

    def get_required_metrics(self) -> List[Metrics]:
        """
        Get the required metrics for the MetricCollector.

        :return: List of required metrics
        """
        return self._required_metrics

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
        with self._lock:
            for key, value in metrics.items():
                self._collected_metrics[key] = value

    def get_detailed_metrics(self) -> List[dict[str, Any]]:
        """
        Retrieve collected metrics.

        :return: Dictionary of collected metrics
        """
        return self._collected_metrics

    def get_aggregated_metrics(self) -> List[dict[str, Any]]:
        """
        Retrieve collected metrics.

        :return: Dictionary of collected metrics
        """
        aggregated_metrics = {}
        for key, value in self._collected_metrics.items():
            new_key = tuple(
                item for item in key if item[0] not in ["flow_index", "component_index"]
            )

            if new_key not in aggregated_metrics:
                aggregated_metrics[new_key] = value
            else:
                # aggregate metrics: sum
                metric = key.metric
                aggregated_timestamp = aggregated_metrics[new_key].timestamp
                metric_value = value.value
                metric_timestamp = value.timestamp

                if metric in [
                    Metrics.SOLCLIENT_STATS_RX_ACKED
                ]:  # add metrics that need to be aggregated by sum
                    aggregated_metrics[new_key].value += sum(metric_value)

                # set timestamp to the latest
                if metric_timestamp > aggregated_timestamp:
                    aggregated_metrics[new_key].timestamp = metric_timestamp

        return aggregated_metrics
