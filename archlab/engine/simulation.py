import heapq
import random
from typing import Dict, List, Optional

from archlab.engine.component import BaseComponent
from archlab.engine.event import Event, EventType
from archlab.engine.metrics import MetricsCollector
from archlab.engine.request import Request


class SimulationEngine:
    def __init__(
        self,
        components: List[BaseComponent],
        entry_component_id: str,
        rps: float,
        duration: float,
        seed: Optional[int] = None,
        stochastic: bool = False,
    ) -> None:
        self.components: Dict[str, BaseComponent] = {c.component_id: c for c in components}
        self.entry_component_id: str = entry_component_id
        self.rps: float = rps
        self.duration: float = duration
        self.seed: Optional[int] = seed
        self.stochastic: bool = stochastic
        self.current_time: float = 0.0
        self.event_queue: List[Event] = []
        self.requests: Dict[int, Request] = {}
        self.metrics: MetricsCollector = MetricsCollector(duration)

    def reset(self) -> None:
        self.current_time = 0.0
        self.event_queue.clear()
        self.requests.clear()
        self.metrics = MetricsCollector(self.duration)
        for component in self.components.values():
            component.queue.clear()
            component.busy_workers = 0
            if hasattr(component, "dropped_requests"):
                component.dropped_requests = 0
            if hasattr(component, "_rr_index"):
                component._rr_index = 0

    def initialize_arrivals(self) -> None:
        if self.stochastic:
            self._initialize_stochastic_arrivals()
        else:
            self._initialize_deterministic_arrivals()

    def _initialize_deterministic_arrivals(self) -> None:
        interval = 1.0 / self.rps
        num_requests = int(self.duration * self.rps)
        for i in range(num_requests):
            timestamp = i * interval
            self._create_arrival(i, timestamp)

    def _initialize_stochastic_arrivals(self) -> None:
        request_id = 0
        timestamp = 0.0
        while True:
            inter_arrival = random.expovariate(self.rps)
            timestamp += inter_arrival
            if timestamp >= self.duration:
                break
            self._create_arrival(request_id, timestamp)
            request_id += 1

    def _create_arrival(self, request_id: int, timestamp: float) -> None:
        request = Request(id=request_id, arrival_time=timestamp)
        self.requests[request_id] = request
        self.metrics.record_generation()
        event = Event(
            timestamp=timestamp,
            event_type=EventType.ARRIVAL,
            request_id=request_id,
            component_id=self.entry_component_id,
        )
        self.schedule_event(event)

    def schedule_event(self, event: Event) -> None:
        heapq.heappush(self.event_queue, event)

    def run(self) -> None:
        if self.seed is not None:
            random.seed(self.seed)
        for comp in self.components.values():
            if hasattr(comp, "workers"):
                self.metrics.register_component(comp.component_id, comp.workers)
        self.initialize_arrivals()
        while self.event_queue:
            event = heapq.heappop(self.event_queue)
            if event.timestamp > self.duration:
                break
            self.current_time = event.timestamp
            self.process_event(event)

    def process_event(self, event: Event) -> None:
        request = self.requests[event.request_id]
        component = self.components[event.component_id]

        if event.event_type == EventType.ARRIVAL:
            new_events = component.handle_arrival(request, self.current_time)
            if new_events:
                for new_event in new_events:
                    self.schedule_event(new_event)

        elif event.event_type == EventType.PROCESS_COMPLETE:
            self.metrics.record_busy_time(component.component_id, event.service_duration)
            self.metrics.record_processed(component.component_id)

            new_events = component.handle_completion(request, self.current_time)
            if new_events:
                for new_event in new_events:
                    self.schedule_event(new_event)

            next_target = component.next_component
            if next_target:
                next_comp = self.components[next_target]
                forward_events = next_comp.handle_arrival(request, self.current_time)
                if forward_events:
                    for forward_event in forward_events:
                        self.schedule_event(forward_event)
            else:
                request.completion_time = self.current_time
                latency = request.completion_time - request.arrival_time
                self.metrics.record_completion(request.id, latency)
