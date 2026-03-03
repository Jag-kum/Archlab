from typing import Any, Dict, List

import yaml

from archlab.engine.component import (
    BaseComponent,
    BoundedQueueComponent,
    Component,
    LoadBalancer,
)
from archlab.engine.distributions import constant, exponential, lognormal
from archlab.engine.simulation import SimulationEngine


def _parse_service_time(raw: Any):
    if isinstance(raw, (int, float)):
        return constant(raw)
    if isinstance(raw, dict):
        dist = raw.get("distribution", "constant")
        if dist == "constant":
            return constant(raw["value"])
        elif dist == "exponential":
            return exponential(raw["mean"])
        elif dist == "lognormal":
            return lognormal(raw["mean"], raw["sigma"])
    raise ValueError(f"Invalid service_time: {raw}")


def _parse_routing(raw: Any):
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        return [(entry["target"], entry["probability"]) for entry in raw]
    raise ValueError(f"Invalid next_component: {raw}")


def _build_component(cfg: Dict[str, Any]) -> BaseComponent:
    comp_type = cfg.get("type", "component")
    comp_id = cfg["id"]
    routing = _parse_routing(cfg.get("next_component"))

    if comp_type == "component":
        return Component(
            component_id=comp_id,
            service_time=_parse_service_time(cfg["service_time"]),
            workers=cfg["workers"],
            next_component=routing,
        )
    elif comp_type == "bounded_queue":
        return BoundedQueueComponent(
            component_id=comp_id,
            service_time=_parse_service_time(cfg["service_time"]),
            workers=cfg["workers"],
            max_queue_size=cfg["max_queue_size"],
            next_component=routing,
        )
    elif comp_type == "load_balancer":
        return LoadBalancer(
            component_id=comp_id,
            targets=cfg["targets"],
            next_component=routing,
        )
    else:
        raise ValueError(f"Unknown component type: {comp_type}")


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def build_engine(config: Dict[str, Any]) -> SimulationEngine:
    components: List[BaseComponent] = []
    for comp_cfg in config["components"]:
        components.append(_build_component(comp_cfg))

    sim_cfg = config["simulation"]
    return SimulationEngine(
        components=components,
        entry_component_id=sim_cfg["entry"],
        rps=sim_cfg["rps"],
        duration=sim_cfg["duration"],
        seed=sim_cfg.get("seed"),
        stochastic=sim_cfg.get("stochastic", False),
    )
