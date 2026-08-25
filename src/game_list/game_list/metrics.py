"""This module contains the custom Prometheus metrics."""

from prometheus_client import Counter, Gauge


class Metrics:
    """A class containing custom metrics."""

    cpu_usage_metric = Gauge("cpu_usage_percent", "CPU usage percentage.")
    memory_usage_metric = Gauge("memory_usage_percent", "Percentage of memory usage.")
    users_registered_total = Counter("users_registered_total", "Total number of registered users.")
    game_lists_entries_created_total = Counter(
        "game_lists_entries_created_total",
        "Total number of game list entries created.",
    )
