"""Validation benchmark: compares ArchLab simulation output against real microservice measurements.

Starts Flask API + DB servers, load tests them, models the same topology in
ArchLab, and compares p95 latency, throughput, and completion rate.

Usage:
    python benchmark/validate.py
    python benchmark/validate.py --rps 8 --duration 15
"""
import argparse
import json
import multiprocessing
import os
import signal
import sys
import time
from typing import Any, Dict

# Add parent to path so we can import archlab
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run_server(role, port, mean_st):
    """Run a Flask server in a subprocess."""
    from benchmark.services import create_api_app, create_db_app
    from werkzeug.serving import make_server

    if role == "api":
        app = create_api_app(mean_service_time=mean_st)
    else:
        app = create_db_app(mean_service_time=mean_st)

    server = make_server("127.0.0.1", port, app, threaded=True)
    server.serve_forever()


def run_real_benchmark(
    api_mean_st: float, db_mean_st: float,
    api_workers: int, db_workers: int,
    rps: float, duration: float, seed: int,
) -> Dict[str, Any]:
    """Start servers, load test, return real metrics."""
    db_proc = multiprocessing.Process(
        target=_run_server, args=("db", 5002, db_mean_st), daemon=True
    )
    api_proc = multiprocessing.Process(
        target=_run_server, args=("api", 5001, api_mean_st), daemon=True
    )

    db_proc.start()
    time.sleep(1.0)
    api_proc.start()
    time.sleep(1.0)

    try:
        from benchmark.loadtest import run_loadtest
        results = run_loadtest(
            url="http://127.0.0.1:5001/request",
            rps=rps, duration=duration, seed=seed,
        )
    finally:
        api_proc.terminate()
        db_proc.terminate()
        api_proc.join(timeout=5)
        db_proc.join(timeout=5)

    return results


def run_archlab_simulation(
    api_mean_st: float, db_mean_st: float,
    api_workers: int, db_workers: int,
    rps: float, duration: float, seeds: list,
) -> Dict[str, Any]:
    """Run ArchLab simulation with the same parameters, averaged over multiple seeds."""
    from archlab.engine.component import Component
    from archlab.engine.distributions import exponential
    from archlab.engine.simulation import SimulationEngine

    all_summaries = []
    for seed in seeds:
        api = Component(
            component_id="api",
            service_time=exponential(mean=api_mean_st),
            workers=api_workers,
            next_component="db",
        )
        db = Component(
            component_id="db",
            service_time=exponential(mean=db_mean_st),
            workers=db_workers,
        )
        engine = SimulationEngine(
            components=[api, db],
            entry_component_id="api",
            rps=rps, duration=duration,
            seed=seed, stochastic=True,
        )
        engine.run()
        all_summaries.append(engine.metrics.summary())

    n = len(all_summaries)
    averaged = {}
    for key in ["generated", "completed", "dropped", "average_latency", "p95_latency", "p99_latency", "throughput"]:
        averaged[key] = sum(s[key] for s in all_summaries) / n
    averaged["bottleneck"] = all_summaries[0].get("bottleneck")

    return averaged


def compare_results(real: Dict, simulated: Dict, tolerance: float = 0.25) -> Dict[str, Any]:
    """Compare real vs simulated metrics and determine if they are within tolerance."""
    comparisons = {}

    metrics_to_compare = [
        ("throughput", "higher_ok"),
        ("p95_latency", "lower_ok"),
        ("average_latency", "lower_ok"),
    ]

    all_pass = True
    for metric, direction in metrics_to_compare:
        real_val = real.get(metric, 0)
        sim_val = simulated.get(metric, 0)

        if real_val > 0:
            error = abs(sim_val - real_val) / real_val
        elif sim_val > 0:
            error = 1.0
        else:
            error = 0.0

        within = error <= tolerance
        if not within:
            all_pass = False

        comparisons[metric] = {
            "real": round(real_val, 4),
            "simulated": round(sim_val, 4),
            "error_pct": round(error * 100, 1),
            "within_tolerance": within,
        }

    real_comp_rate = real["completed"] / real["generated"] if real["generated"] > 0 else 0
    sim_comp_rate = simulated["completed"] / simulated["generated"] if simulated["generated"] > 0 else 0
    rate_error = abs(real_comp_rate - sim_comp_rate)
    rate_ok = rate_error <= tolerance
    if not rate_ok:
        all_pass = False

    comparisons["completion_rate"] = {
        "real": round(real_comp_rate, 4),
        "simulated": round(sim_comp_rate, 4),
        "error_pct": round(rate_error * 100, 1),
        "within_tolerance": rate_ok,
    }

    comparisons["all_within_tolerance"] = all_pass
    comparisons["tolerance"] = f"{tolerance:.0%}"

    return comparisons


def main():
    parser = argparse.ArgumentParser(description="ArchLab Validation Benchmark")
    parser.add_argument("--api-mean-st", type=float, default=0.15, help="API mean service time")
    parser.add_argument("--db-mean-st", type=float, default=0.4, help="DB mean service time")
    parser.add_argument("--api-workers", type=int, default=4, help="API concurrent workers")
    parser.add_argument("--db-workers", type=int, default=4, help="DB concurrent workers")
    parser.add_argument("--rps", type=float, default=5.0, help="Requests per second")
    parser.add_argument("--duration", type=float, default=15.0, help="Test duration in seconds")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for load test")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    print("=" * 60)
    print("  ArchLab Validation Benchmark")
    print("=" * 60)
    print(f"  Topology: api (mean={args.api_mean_st}s, w={args.api_workers}) -> db (mean={args.db_mean_st}s, w={args.db_workers})")
    print(f"  Load: {args.rps} RPS for {args.duration}s")
    print()

    print("[1/3] Running real microservices benchmark...")
    real = run_real_benchmark(
        api_mean_st=args.api_mean_st, db_mean_st=args.db_mean_st,
        api_workers=args.api_workers, db_workers=args.db_workers,
        rps=args.rps, duration=args.duration, seed=args.seed,
    )

    print("[2/3] Running ArchLab simulation (5 seeds)...")
    sim_seeds = [args.seed, args.seed + 1, args.seed + 2, args.seed + 3, args.seed + 4]
    simulated = run_archlab_simulation(
        api_mean_st=args.api_mean_st, db_mean_st=args.db_mean_st,
        api_workers=args.api_workers, db_workers=args.db_workers,
        rps=args.rps, duration=args.duration, seeds=sim_seeds,
    )

    print("[3/3] Comparing results...")
    comparison = compare_results(real, simulated)

    if args.json:
        print(json.dumps({"real": real, "simulated": simulated, "comparison": comparison}, indent=2))
    else:
        print()
        print(f"  {'Metric':<20} {'Real':>10} {'Simulated':>10} {'Error':>8} {'Status':>8}")
        print("  " + "-" * 60)
        for metric, data in comparison.items():
            if isinstance(data, dict):
                status = "PASS" if data["within_tolerance"] else "FAIL"
                print(f"  {metric:<20} {data['real']:>10.4f} {data['simulated']:>10.4f} {data['error_pct']:>7.1f}% {'  ' + status:>8}")
        print()
        overall = "PASS" if comparison["all_within_tolerance"] else "FAIL"
        print(f"  Overall: {overall} (tolerance: {comparison['tolerance']})")
        print()


if __name__ == "__main__":
    main()
