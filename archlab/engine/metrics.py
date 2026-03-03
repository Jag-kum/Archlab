from typing import Any, Dict, List, Optional


class MetricsCollector:
    def __init__(self, simulation_duration: float) -> None:
        self.simulation_duration: float = simulation_duration
        self.completed_requests: int = 0
        self.generated_requests: int = 0
        self.latencies: List[float] = []
        self.component_busy_time: Dict[str, float] = {}
        self.component_processed: Dict[str, int] = {}
        self.component_workers: Dict[str, int] = {}

    def register_component(self, component_id: str, workers: int) -> None:
        self.component_workers[component_id] = workers

    def record_generation(self) -> None:
        self.generated_requests += 1

    def record_completion(self, request_id: int, latency: float) -> None:
        self.completed_requests += 1
        self.latencies.append(latency)

    def record_busy_time(self, component_id: str, duration: float) -> None:
        if component_id not in self.component_busy_time:
            self.component_busy_time[component_id] = 0.0
        self.component_busy_time[component_id] += duration

    def record_processed(self, component_id: str) -> None:
        if component_id not in self.component_processed:
            self.component_processed[component_id] = 0
        self.component_processed[component_id] += 1

    def summary(self, sla: Optional[Dict[str, Any]] = None) -> dict:
        if self.latencies:
            average_latency = sum(self.latencies) / len(self.latencies)
            sorted_latencies = sorted(self.latencies)
            p95_index = int(len(sorted_latencies) * 0.95)
            p95_index = min(p95_index, len(sorted_latencies) - 1)
            p95_latency = sorted_latencies[p95_index]
            p99_index = int(len(sorted_latencies) * 0.99)
            p99_index = min(p99_index, len(sorted_latencies) - 1)
            p99_latency = sorted_latencies[p99_index]
        else:
            average_latency = 0.0
            p95_latency = 0.0
            p99_latency = 0.0

        if self.simulation_duration > 0:
            throughput = self.completed_requests / self.simulation_duration
        else:
            throughput = 0.0

        if self.simulation_duration > 0:
            component_utilization = {
                cid: busy / self.simulation_duration
                for cid, busy in self.component_busy_time.items()
            }
        else:
            component_utilization = {}

        dropped = self.generated_requests - self.completed_requests

        bottleneck = self._detect_bottleneck(component_utilization)

        result: Dict[str, Any] = {
            "generated": self.generated_requests,
            "completed": self.completed_requests,
            "dropped": dropped,
            "average_latency": average_latency,
            "p95_latency": p95_latency,
            "p99_latency": p99_latency,
            "throughput": throughput,
            "component_utilization": component_utilization,
            "bottleneck": bottleneck,
        }

        if sla:
            result["sla"] = self._check_sla(sla, result)

        return result

    def _detect_bottleneck(self, component_utilization: Dict[str, float]) -> Optional[str]:
        if not component_utilization:
            return None
        per_worker_util = {}
        for cid, util in component_utilization.items():
            workers = self.component_workers.get(cid, 1)
            per_worker_util[cid] = util / workers
        return max(per_worker_util, key=per_worker_util.get)

    def _check_sla(self, sla: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
        checks: Dict[str, Any] = {}
        if "max_p95_latency" in sla:
            actual = results["p95_latency"]
            threshold = sla["max_p95_latency"]
            checks["max_p95_latency"] = {
                "threshold": threshold,
                "actual": actual,
                "passed": actual <= threshold,
            }
        if "max_p99_latency" in sla:
            actual = results["p99_latency"]
            threshold = sla["max_p99_latency"]
            checks["max_p99_latency"] = {
                "threshold": threshold,
                "actual": actual,
                "passed": actual <= threshold,
            }
        if "min_throughput" in sla:
            actual = results["throughput"]
            threshold = sla["min_throughput"]
            checks["min_throughput"] = {
                "threshold": threshold,
                "actual": actual,
                "passed": actual >= threshold,
            }
        if "max_drop_rate" in sla:
            if results["generated"] > 0:
                actual = results["dropped"] / results["generated"]
            else:
                actual = 0.0
            threshold = sla["max_drop_rate"]
            checks["max_drop_rate"] = {
                "threshold": threshold,
                "actual": actual,
                "passed": actual <= threshold,
            }
        checks["all_passed"] = all(c["passed"] for c in checks.values() if isinstance(c, dict))
        return checks
