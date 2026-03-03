"""Concurrent load tester that sends requests at a target RPS and collects latency metrics.

Uses threading to generate concurrent load against the API server.
Returns the same metric structure as ArchLab's MetricsCollector.summary().
"""
import random
import statistics
import threading
import time
from typing import Any, Dict, List


def run_loadtest(
    url: str = "http://127.0.0.1:5001/request",
    rps: float = 5.0,
    duration: float = 20.0,
    seed: int = 42,
) -> Dict[str, Any]:
    """Send requests at Poisson-distributed arrival times and measure latencies."""
    import requests as req_lib

    random.seed(seed)

    latencies: List[float] = []
    errors = 0
    lock = threading.Lock()

    def send_one():
        nonlocal errors
        start = time.monotonic()
        try:
            resp = req_lib.get(url, timeout=30)
            elapsed = time.monotonic() - start
            if resp.status_code == 200:
                with lock:
                    latencies.append(elapsed)
            else:
                with lock:
                    errors += 1
        except Exception:
            with lock:
                errors += 1

    arrival_times = []
    t = 0.0
    while t < duration:
        t += random.expovariate(rps)
        if t < duration:
            arrival_times.append(t)

    generated = len(arrival_times)
    start_wall = time.monotonic()

    threads = []
    for arrival in arrival_times:
        wait = arrival - (time.monotonic() - start_wall)
        if wait > 0:
            time.sleep(wait)
        th = threading.Thread(target=send_one)
        th.start()
        threads.append(th)

    for th in threads:
        th.join(timeout=60)

    completed = len(latencies)
    dropped = generated - completed

    if latencies:
        sorted_lat = sorted(latencies)
        avg = statistics.mean(sorted_lat)
        p95_idx = min(int(len(sorted_lat) * 0.95), len(sorted_lat) - 1)
        p99_idx = min(int(len(sorted_lat) * 0.99), len(sorted_lat) - 1)
        p95 = sorted_lat[p95_idx]
        p99 = sorted_lat[p99_idx]
    else:
        avg = p95 = p99 = 0.0

    actual_duration = time.monotonic() - start_wall
    throughput = completed / actual_duration if actual_duration > 0 else 0.0

    return {
        "generated": generated,
        "completed": completed,
        "dropped": dropped,
        "errors": errors,
        "average_latency": avg,
        "p95_latency": p95,
        "p99_latency": p99,
        "throughput": throughput,
        "actual_duration": actual_duration,
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Load test a URL at a target RPS")
    parser.add_argument("--url", default="http://127.0.0.1:5001/request")
    parser.add_argument("--rps", type=float, default=5.0)
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print(f"Load testing {args.url} at {args.rps} RPS for {args.duration}s...")
    results = run_loadtest(args.url, args.rps, args.duration, args.seed)
    print(json.dumps(results, indent=2))
