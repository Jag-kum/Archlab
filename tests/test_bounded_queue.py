from archlab.engine.component import BoundedQueueComponent
from archlab.engine.event import EventType
from archlab.engine.request import Request
from archlab.engine.simulation import SimulationEngine


class TestBoundedQueueArrival:
    def test_free_worker_processes_immediately(self):
        comp = BoundedQueueComponent(
            component_id="svc", service_time=1.0, workers=2, max_queue_size=5,
        )
        req = Request(id=0, arrival_time=0.0)
        events = comp.handle_arrival(req, current_time=0.0)

        assert len(events) == 1
        assert events[0].event_type == EventType.PROCESS_COMPLETE
        assert comp.busy_workers == 1
        assert comp.dropped_requests == 0

    def test_queues_when_workers_busy(self):
        comp = BoundedQueueComponent(
            component_id="svc", service_time=1.0, workers=1, max_queue_size=3,
        )
        comp.handle_arrival(Request(id=0, arrival_time=0.0), current_time=0.0)
        events = comp.handle_arrival(Request(id=1, arrival_time=0.1), current_time=0.1)

        assert len(events) == 0
        assert len(comp.queue) == 1
        assert comp.dropped_requests == 0

    def test_drops_when_queue_full(self):
        comp = BoundedQueueComponent(
            component_id="svc", service_time=1.0, workers=1, max_queue_size=2,
        )
        comp.handle_arrival(Request(id=0, arrival_time=0.0), current_time=0.0)
        comp.handle_arrival(Request(id=1, arrival_time=0.1), current_time=0.1)
        comp.handle_arrival(Request(id=2, arrival_time=0.2), current_time=0.2)

        events = comp.handle_arrival(Request(id=3, arrival_time=0.3), current_time=0.3)

        assert len(events) == 0
        assert len(comp.queue) == 2
        assert comp.dropped_requests == 1

    def test_multiple_drops_counted(self):
        comp = BoundedQueueComponent(
            component_id="svc", service_time=1.0, workers=1, max_queue_size=0,
        )
        comp.handle_arrival(Request(id=0, arrival_time=0.0), current_time=0.0)

        for i in range(1, 6):
            comp.handle_arrival(Request(id=i, arrival_time=0.1 * i), current_time=0.1 * i)

        assert comp.dropped_requests == 5
        assert comp.busy_workers == 1


class TestBoundedQueueCompletion:
    def test_drains_queue_on_completion(self):
        comp = BoundedQueueComponent(
            component_id="svc", service_time=1.0, workers=1, max_queue_size=5,
        )
        comp.handle_arrival(Request(id=0, arrival_time=0.0), current_time=0.0)
        comp.handle_arrival(Request(id=1, arrival_time=0.1), current_time=0.1)

        events = comp.handle_completion(Request(id=0, arrival_time=0.0), current_time=1.0)

        assert len(events) == 1
        assert events[0].request_id == 1
        assert len(comp.queue) == 0

    def test_empty_queue_on_completion(self):
        comp = BoundedQueueComponent(
            component_id="svc", service_time=1.0, workers=1, max_queue_size=5,
        )
        comp.handle_arrival(Request(id=0, arrival_time=0.0), current_time=0.0)

        events = comp.handle_completion(Request(id=0, arrival_time=0.0), current_time=1.0)

        assert len(events) == 0
        assert comp.busy_workers == 0


class TestBoundedQueueIntegration:
    def test_in_simulation_drops_excess(self):
        comp = BoundedQueueComponent(
            component_id="app", service_time=1.0, workers=1, max_queue_size=2,
        )
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=5, duration=3,
        )
        engine.run()

        assert comp.dropped_requests > 0
        assert engine.metrics.generated_requests == 15

    def test_zero_queue_only_processes_worker_count(self):
        comp = BoundedQueueComponent(
            component_id="app", service_time=0.5, workers=2, max_queue_size=0,
        )
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=10, duration=2,
        )
        engine.run()

        assert comp.dropped_requests > 0
        assert engine.metrics.completed_requests < engine.metrics.generated_requests
