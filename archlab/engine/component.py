import random
from abc import ABC, abstractmethod
from collections import deque
from typing import Callable, List, Optional, Tuple, Union

from archlab.engine.distributions import constant
from archlab.engine.event import Event, EventType
from archlab.engine.request import Request

ServiceTime = Union[float, Callable[[], float]]
Routing = Union[None, str, List[Tuple[str, float]]]


def _make_service_time_fn(service_time: ServiceTime) -> Callable[[], float]:
    if isinstance(service_time, (int, float)):
        return constant(service_time)
    return service_time


def _normalize_routing(routing: Routing) -> Optional[List[Tuple[str, float]]]:
    if routing is None:
        return None
    if isinstance(routing, str):
        return [(routing, 1.0)]
    return routing


def resolve_next_component(routing: Optional[List[Tuple[str, float]]]) -> Optional[str]:
    if routing is None:
        return None
    r = random.random()
    cumulative = 0.0
    for target, probability in routing:
        cumulative += probability
        if r < cumulative:
            return target
    return routing[-1][0]


class BaseComponent(ABC):
    def __init__(
        self,
        component_id: str,
        next_component: Routing = None,
    ) -> None:
        self.component_id: str = component_id
        self._routing: Optional[List[Tuple[str, float]]] = _normalize_routing(next_component)
        self.queue: deque = deque()
        self.busy_workers: int = 0

    @property
    def next_component(self) -> Optional[str]:
        return resolve_next_component(self._routing)

    @abstractmethod
    def handle_arrival(self, request: Request, current_time: float) -> List[Event]:
        pass

    @abstractmethod
    def handle_completion(self, request: Request, current_time: float) -> List[Event]:
        pass


class Component(BaseComponent):
    """Standard worker-pool component with configurable service time and concurrency."""

    def __init__(
        self,
        component_id: str,
        service_time: ServiceTime,
        workers: int,
        next_component: Routing = None,
    ) -> None:
        super().__init__(component_id, next_component)
        self._service_time_fn: Callable[[], float] = _make_service_time_fn(service_time)
        self.workers: int = workers

    @property
    def service_time(self) -> float:
        return self._service_time_fn()

    def handle_arrival(self, request: Request, current_time: float) -> List[Event]:
        if self.busy_workers < self.workers:
            self.busy_workers += 1
            duration = self.service_time
            event = Event(
                timestamp=current_time + duration,
                event_type=EventType.PROCESS_COMPLETE,
                request_id=request.id,
                component_id=self.component_id,
                service_duration=duration,
            )
            return [event]
        else:
            self.queue.append(request)
            return []

    def handle_completion(self, request: Request, current_time: float) -> List[Event]:
        self.busy_workers -= 1
        if self.queue:
            next_request = self.queue.popleft()
            self.busy_workers += 1
            duration = self.service_time
            event = Event(
                timestamp=current_time + duration,
                event_type=EventType.PROCESS_COMPLETE,
                request_id=next_request.id,
                component_id=self.component_id,
                service_duration=duration,
            )
            return [event]
        else:
            return []


class BoundedQueueComponent(BaseComponent):
    """Worker-pool component that drops requests when the queue exceeds max_queue_size."""

    def __init__(
        self,
        component_id: str,
        service_time: ServiceTime,
        workers: int,
        max_queue_size: int,
        next_component: Routing = None,
    ) -> None:
        super().__init__(component_id, next_component)
        self._service_time_fn: Callable[[], float] = _make_service_time_fn(service_time)
        self.workers: int = workers
        self.max_queue_size: int = max_queue_size
        self.dropped_requests: int = 0

    @property
    def service_time(self) -> float:
        return self._service_time_fn()

    def handle_arrival(self, request: Request, current_time: float) -> List[Event]:
        if self.busy_workers < self.workers:
            self.busy_workers += 1
            duration = self.service_time
            event = Event(
                timestamp=current_time + duration,
                event_type=EventType.PROCESS_COMPLETE,
                request_id=request.id,
                component_id=self.component_id,
                service_duration=duration,
            )
            return [event]
        elif len(self.queue) < self.max_queue_size:
            self.queue.append(request)
            return []
        else:
            self.dropped_requests += 1
            return []

    def handle_completion(self, request: Request, current_time: float) -> List[Event]:
        self.busy_workers -= 1
        if self.queue:
            next_request = self.queue.popleft()
            self.busy_workers += 1
            duration = self.service_time
            event = Event(
                timestamp=current_time + duration,
                event_type=EventType.PROCESS_COMPLETE,
                request_id=next_request.id,
                component_id=self.component_id,
                service_duration=duration,
            )
            return [event]
        else:
            return []


class LoadBalancer(BaseComponent):
    """Routes incoming requests to target components using round-robin selection."""

    def __init__(
        self,
        component_id: str,
        targets: List[str],
        next_component: Routing = None,
    ) -> None:
        super().__init__(component_id, next_component)
        self.targets: List[str] = targets
        self._rr_index: int = 0

    def handle_arrival(self, request: Request, current_time: float) -> List[Event]:
        target_id = self.targets[self._rr_index % len(self.targets)]
        self._rr_index += 1
        event = Event(
            timestamp=current_time,
            event_type=EventType.ARRIVAL,
            request_id=request.id,
            component_id=target_id,
        )
        return [event]

    def handle_completion(self, request: Request, current_time: float) -> List[Event]:
        return []
