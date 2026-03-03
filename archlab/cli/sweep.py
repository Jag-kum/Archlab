import copy
from typing import Any, Dict, List, Optional

from archlab.cli.config import build_engine


def _set_nested(data: Dict[str, Any], dotpath: str, value: Any) -> None:
    """Set a value in a nested dict using dot notation like 'db.workers'."""
    keys = dotpath.split(".")
    target = data
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value


def _find_component_field(config: Dict[str, Any], dotpath: str):
    """Resolve 'component_id.field' into the component dict and field name."""
    parts = dotpath.split(".")
    if len(parts) != 2:
        raise ValueError(f"Parameter path must be 'component_id.field' or 'simulation.field', got: {dotpath}")

    comp_id, field = parts

    if comp_id == "simulation":
        return config["simulation"], field

    for comp_cfg in config["components"]:
        if comp_cfg["id"] == comp_id:
            return comp_cfg, field

    raise ValueError(f"Component '{comp_id}' not found in config")


def _apply_param(config: Dict[str, Any], param: str, value: Any) -> Dict[str, Any]:
    """Create a deep copy of config with the given parameter set to value."""
    cfg = copy.deepcopy(config)
    target, field = _find_component_field(cfg, param)
    target[field] = value
    return cfg


def run_sweep(
    config: Dict[str, Any],
    param: str,
    values: List[Any],
    seeds: Optional[List[int]] = None,
    sla: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Run a parameter sweep over a base config.

    For each value in `values`, modifies the parameter identified by `param`
    (dot notation like "db.workers" or "simulation.rps"), builds an engine,
    runs the simulation, and collects the summary.

    If `seeds` is provided, runs each config len(seeds) times with different
    seeds and averages the numeric results for statistical confidence.
    """
    results = []

    for value in values:
        modified_config = _apply_param(config, param, value)

        if seeds and len(seeds) > 1:
            summaries = []
            for seed in seeds:
                modified_config["simulation"]["seed"] = seed
                modified_config["simulation"]["stochastic"] = True
                engine = build_engine(modified_config)
                engine.run()
                summaries.append(engine.metrics.summary(sla=sla))
            averaged = _average_summaries(summaries)
            averaged["param_value"] = value
            averaged["runs"] = len(seeds)
            results.append(averaged)
        else:
            engine = build_engine(modified_config)
            engine.run()
            summary = engine.metrics.summary(sla=sla)
            summary["param_value"] = value
            summary["runs"] = 1
            results.append(summary)

    return results


def _average_summaries(summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Average numeric fields across multiple simulation runs."""
    n = len(summaries)
    averaged: Dict[str, Any] = {}

    numeric_keys = [
        "generated", "completed", "dropped",
        "average_latency", "p95_latency", "p99_latency", "throughput",
    ]
    for key in numeric_keys:
        averaged[key] = sum(s[key] for s in summaries) / n

    all_comp_ids = set()
    for s in summaries:
        all_comp_ids.update(s.get("component_utilization", {}).keys())

    averaged["component_utilization"] = {}
    for cid in all_comp_ids:
        vals = [s.get("component_utilization", {}).get(cid, 0.0) for s in summaries]
        averaged["component_utilization"][cid] = sum(vals) / n

    bottlenecks = [s.get("bottleneck") for s in summaries]
    averaged["bottleneck"] = max(set(bottlenecks), key=bottlenecks.count)

    if "sla" in summaries[0]:
        pass_counts = sum(1 for s in summaries if s.get("sla", {}).get("all_passed", False))
        averaged["sla_pass_rate"] = pass_counts / n

    return averaged


def format_sweep_table(results: List[Dict[str, Any]], param: str) -> str:
    """Format sweep results as a readable table."""
    lines = []
    header = (
        f"{'Value':>10} | {'Generated':>10} | {'Completed':>10} | {'Dropped':>8} | "
        f"{'Avg Lat':>8} | {'P95 Lat':>8} | {'P99 Lat':>8} | "
        f"{'Thruput':>8} | {'Bottleneck':>12}"
    )
    lines.append(f"\nParameter Sweep: {param}")
    lines.append("-" * len(header))
    lines.append(header)
    lines.append("-" * len(header))

    for r in results:
        val = r["param_value"]
        gen = r["generated"]
        comp = r["completed"]
        drop = r["dropped"]
        avg = r["average_latency"]
        p95 = r["p95_latency"]
        p99 = r["p99_latency"]
        thru = r["throughput"]
        bn = r.get("bottleneck", "-") or "-"

        gen_s = f"{gen:.0f}" if isinstance(gen, float) else str(gen)
        comp_s = f"{comp:.0f}" if isinstance(comp, float) else str(comp)
        drop_s = f"{drop:.0f}" if isinstance(drop, float) else str(drop)

        lines.append(
            f"{str(val):>10} | {gen_s:>10} | {comp_s:>10} | {drop_s:>8} | "
            f"{avg:>8.3f} | {p95:>8.3f} | {p99:>8.3f} | "
            f"{thru:>8.3f} | {bn:>12}"
        )

    lines.append("-" * len(header))

    if "sla_pass_rate" in results[0]:
        lines.append("")
        lines.append("SLA Pass Rate per config:")
        for r in results:
            rate = r.get("sla_pass_rate", "N/A")
            if isinstance(rate, float):
                lines.append(f"  {r['param_value']}: {rate:.0%}")

    return "\n".join(lines)
