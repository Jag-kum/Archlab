from archlab.engine.component import BoundedQueueComponent, Component, LoadBalancer
from archlab.engine.distributions import exponential
from archlab.engine.simulation import SimulationEngine
from archlab.cli.sweep import format_sweep_table, run_sweep


def print_summary(label, engine, sla=None):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    summary = engine.metrics.summary(sla=sla)
    for key, value in summary.items():
        if key == "sla":
            print(f"  sla:")
            for check_name, check in value.items():
                if isinstance(check, dict):
                    status = "PASS" if check["passed"] else "FAIL"
                    print(f"    [{status}] {check_name}: {check['actual']:.4f} (limit: {check['threshold']})")
                else:
                    print(f"    all_passed: {check}")
        elif isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        elif isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v:.4f}" if isinstance(v, float) else f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")


# --- 1. Bottleneck Detection ---
fast = Component(component_id="api", service_time=0.1, workers=10, next_component="db")
slow = Component(component_id="db", service_time=exponential(mean=0.8), workers=2)

engine = SimulationEngine(
    components=[fast, slow], entry_component_id="api",
    rps=5, duration=20, seed=42, stochastic=True,
)
engine.run()
print_summary("Bottleneck Detection | api(10w) -> db(2w)", engine)


# --- 2. Cache Branching with SLA ---
app = Component(
    component_id="app", service_time=exponential(mean=0.2), workers=5,
    next_component=[("cache", 0.8), ("db", 0.2)],
)
cache = Component(component_id="cache", service_time=0.05, workers=10)
db = Component(component_id="db", service_time=exponential(mean=0.5), workers=3)

engine = SimulationEngine(
    components=[app, cache, db], entry_component_id="app",
    rps=20, duration=30, seed=42, stochastic=True,
)
engine.run()

sla = {"max_p95_latency": 2.0, "max_p99_latency": 5.0, "min_throughput": 15.0, "max_drop_rate": 0.1}
print_summary("Cache Branching + SLA Check", engine, sla=sla)


# --- 3. LB -> Bounded Queue -> DB with SLA ---
lb = LoadBalancer(component_id="lb", targets=["app1", "app2"])
app1 = BoundedQueueComponent(
    component_id="app1", service_time=exponential(mean=0.3),
    workers=3, max_queue_size=10, next_component="db",
)
app2 = BoundedQueueComponent(
    component_id="app2", service_time=exponential(mean=0.3),
    workers=3, max_queue_size=10, next_component="db",
)
db = Component(component_id="db", service_time=exponential(mean=0.5), workers=2)

engine = SimulationEngine(
    components=[lb, app1, app2, db], entry_component_id="lb",
    rps=10, duration=30, seed=42, stochastic=True,
)
engine.run()

sla = {"max_p95_latency": 3.0, "min_throughput": 5.0, "max_drop_rate": 0.2}
print_summary("Full Architecture + SLA", engine, sla=sla)


# --- 4. Parameter Sweep: DB Worker Capacity Planning ---
print(f"\n\n{'#'*60}")
print("  Phase 7: Parameter Sweeps")
print(f"{'#'*60}")

config = {
    "components": [
        {"id": "api", "type": "component", "service_time": {"distribution": "exponential", "mean": 0.2}, "workers": 5, "next_component": "db"},
        {"id": "db", "type": "component", "service_time": {"distribution": "exponential", "mean": 0.8}, "workers": 3},
    ],
    "simulation": {"entry": "api", "rps": 8, "duration": 30, "seed": 42, "stochastic": True},
}

print("\n--- Single-run sweep: db.workers from 1 to 8 ---")
results = run_sweep(config, "db.workers", [1, 2, 3, 4, 5, 6, 8])
print(format_sweep_table(results, "db.workers"))

print("\n--- Multi-seed averaged sweep (5 seeds) ---")
results = run_sweep(
    config, "db.workers", [1, 2, 4, 6, 8, 10],
    seeds=[42, 100, 200, 300, 400],
)
print(format_sweep_table(results, "db.workers"))

print("\n--- RPS sweep: how much load can 3 db workers handle? ---")
results = run_sweep(
    config, "simulation.rps", [2, 4, 6, 8, 10, 15, 20],
    seeds=[42, 100, 200],
)
print(format_sweep_table(results, "simulation.rps"))
