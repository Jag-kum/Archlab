# ArchLab

**A discrete-event simulator for distributed system capacity planning and bottleneck detection.**

[![CI](https://github.com/Jag-kum/archlab/actions/workflows/ci.yml/badge.svg)](https://github.com/Jag-kum/archlab/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

ArchLab lets you model distributed architectures — load balancers, worker pools, bounded queues, caching layers — and simulate them under load to find bottlenecks, validate SLAs, and plan capacity, all before writing infrastructure code.

## Features

- **Visual Architecture Designer** — drag-and-drop components onto a canvas, connect them by drawing wires between ports
- **Component Types** — Service (worker pool), Bounded Queue (drops overflow), Load Balancer (round-robin)
- **Stochastic Modeling** — exponential, lognormal, and constant service time distributions with seeded reproducibility
- **Flexible Routing** — deterministic chains, probabilistic branching (e.g., 80% cache hit / 20% miss), DAG topologies
- **Bottleneck Detection** — automatically identifies the component with the highest per-worker utilization
- **SLA Checking** — validate p95, p99 latency, throughput, and drop rate against custom thresholds
- **Parameter Sweeps** — sweep any parameter (workers, RPS, etc.) across a range of values with multi-seed averaging
- **CLI + Web UI + REST API** — use from the terminal, a browser, or integrate programmatically
- **148 automated tests** covering the full engine, CLI, API, and all component types
- **Validated against real microservices** — benchmark shows <5% throughput error vs live Flask services

## Quick Start

### Install

```bash
git clone https://github.com/Jag-kum/archlab.git
cd archlab
pip install -e ".[dev,web]"
```

### Run the Web UI

```bash
python -m archlab serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) — drag components from the palette, connect them, and click **Run Simulation**.

### Run from CLI

```bash
# Single simulation
python -m archlab simulate examples/web_stack.yaml

# Parameter sweep
python -m archlab sweep examples/web_stack.yaml --param db.workers --values 1,2,3,4,5,6,8

# Multi-seed averaged sweep
python -m archlab sweep examples/capacity_planning.yaml \
  --param db.workers --values 1,3,5,7,10 \
  --seeds 42,100,200,300,400
```

### Run from Python

```python
from archlab.engine import Component, SimulationEngine
from archlab.engine.distributions import exponential

api = Component("api", service_time=exponential(mean=0.2), workers=5, next_component="db")
db = Component("db", service_time=exponential(mean=0.8), workers=3)

engine = SimulationEngine(
    components=[api, db],
    entry_component_id="api",
    rps=8, duration=30,
    seed=42, stochastic=True,
)
engine.run()

summary = engine.metrics.summary()
print(f"Throughput: {summary['throughput']:.1f}/s")
print(f"P95 Latency: {summary['p95_latency']:.2f}s")
print(f"Bottleneck: {summary['bottleneck']}")
```

## Example Output

```
Parameter Sweep: db.workers
----------------------------------------------------------------------------------------------------------
     Value |  Generated |  Completed |  Dropped |  Avg Lat |  P95 Lat |  P99 Lat |  Thruput |   Bottleneck
----------------------------------------------------------------------------------------------------------
         1 |        238 |         38 |      200 |   14.350 |   24.313 |   24.995 |    1.253 |           db
         2 |        238 |         69 |      169 |   11.016 |   19.690 |   20.945 |    2.300 |           db
         4 |        238 |        133 |      105 |    6.761 |   12.897 |   13.585 |    4.433 |           db
         6 |        238 |        207 |       31 |    2.729 |    4.868 |    5.783 |    6.900 |           db
         8 |        238 |        227 |       11 |    1.194 |    2.885 |    4.048 |    7.573 |           db
        10 |        238 |        228 |       10 |    1.028 |    2.557 |    3.895 |    7.607 |           db
```

## Architecture

```
archlab/
├── engine/           # Core simulation (zero external dependencies)
│   ├── event.py          # Event dataclass + min-heap ordering
│   ├── request.py        # Request dataclass
│   ├── component.py      # BaseComponent, Component, BoundedQueueComponent, LoadBalancer
│   ├── distributions.py  # constant, exponential, lognormal factories
│   ├── metrics.py        # MetricsCollector with bottleneck detection + SLA
│   └── simulation.py     # SimulationEngine (DES event loop)
├── cli/              # YAML config loading + parameter sweeps
│   ├── config.py         # YAML → Engine builder
│   └── sweep.py          # Parameter sweep engine
├── api/              # FastAPI web layer (thin wrapper)
│   ├── app.py            # POST /simulate, POST /sweep, GET /
│   ├── schemas.py        # Pydantic request models
│   └── static/index.html # Visual drag-and-drop UI
├── __main__.py       # CLI entry point (simulate, sweep, serve)
├── examples/         # YAML config examples
├── benchmark/        # Validation against real Flask microservices
└── tests/            # 148 pytest tests
```

The engine is **framework-agnostic** — it uses only Python's standard library (heapq, random, dataclasses, abc). The CLI adds PyYAML, and the web UI adds FastAPI. Each layer is independently testable.

## YAML Configuration

Define architectures as code:

```yaml
components:
  - id: lb
    type: load_balancer
    targets: [app1, app2]

  - id: app1
    type: component
    service_time:
      distribution: exponential
      mean: 0.3
    workers: 4
    next_component: db

  - id: app2
    type: component
    service_time:
      distribution: exponential
      mean: 0.3
    workers: 4
    next_component: db

  - id: db
    type: component
    service_time:
      distribution: exponential
      mean: 0.8
    workers: 3

simulation:
  entry: lb
  rps: 10
  duration: 30
  seed: 42
  stochastic: true
```

## REST API

```bash
# Run a simulation
curl -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -d '{"components":[{"id":"app","type":"component","service_time":0.5,"workers":2}],"simulation":{"entry":"app","rps":5,"duration":10}}'

# Run a parameter sweep
curl -X POST http://localhost:8000/sweep \
  -H "Content-Type: application/json" \
  -d '{"components":[...],"simulation":{...},"param":"app.workers","values":[1,2,3,5]}'
```

## Validation Benchmark

ArchLab's predictions have been validated against real Flask microservices.
The benchmark starts two Flask apps (API + DB with `time.sleep()` for processing),
load tests them at 5 RPS, then models the identical topology in ArchLab and compares:

```
  Metric                     Real  Simulated    Error   Status
  ------------------------------------------------------------
  throughput               5.3823     5.3600     0.4%     PASS
  p95_latency              1.2030     1.4211    18.1%     PASS
  average_latency          0.5953     0.5834     2.0%     PASS
  completion_rate          1.0000     0.9640     3.6%     PASS

  Overall: PASS (tolerance: 25%)
```

Run it yourself:

```bash
pip install flask requests
python benchmark/validate.py --rps 5 --duration 15
```

## Running Tests

```bash
pip install -e ".[dev,web]"
python -m pytest tests/ -v
```

## License

[MIT](LICENSE)
