from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ServiceTimeDistribution(BaseModel):
    distribution: str = "constant"
    value: Optional[float] = None
    mean: Optional[float] = None
    sigma: Optional[float] = None


class RoutingEntry(BaseModel):
    target: str
    probability: float


class ComponentConfig(BaseModel):
    id: str
    type: str = "component"
    service_time: Optional[Union[float, int, ServiceTimeDistribution]] = None
    workers: Optional[int] = None
    max_queue_size: Optional[int] = None
    targets: Optional[List[str]] = None
    next_component: Optional[Union[str, List[RoutingEntry]]] = None


class SimulationConfig(BaseModel):
    entry: str
    rps: float
    duration: float
    seed: Optional[int] = None
    stochastic: bool = False


class SimulateRequest(BaseModel):
    components: List[ComponentConfig]
    simulation: SimulationConfig
    sla: Optional[Dict[str, Any]] = None


class SweepRequest(BaseModel):
    components: List[ComponentConfig]
    simulation: SimulationConfig
    param: str = Field(description="Dot-path parameter to sweep, e.g. 'db.workers'")
    values: List[Any] = Field(description="Values to try for the parameter")
    seeds: Optional[List[int]] = None
    sla: Optional[Dict[str, Any]] = None
