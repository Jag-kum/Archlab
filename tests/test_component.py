from archlab.engine.component import Component
from archlab.engine.event import EventType
from archlab.engine.request import Request


class TestComponentArrival:
    def test_arrival_with_free_worker_returns_event(self):
        comp = Component(component_id="svc", service_time=2.0, workers=1)
        req = Request(id=0, arrival_time=0.0)
        events = comp.handle_arrival(req, current_time=0.0)

        assert len(events) == 1
        assert events[0].event_type == EventType.PROCESS_COMPLETE
        assert events[0].timestamp == 2.0
        assert events[0].request_id == 0
        assert events[0].component_id == "svc"
        assert comp.busy_workers == 1

    def test_arrival_when_all_workers_busy_queues_request(self):
        comp = Component(component_id="svc", service_time=1.0, workers=1)
        r0 = Request(id=0, arrival_time=0.0)
        r1 = Request(id=1, arrival_time=0.5)

        comp.handle_arrival(r0, current_time=0.0)
        events = comp.handle_arrival(r1, current_time=0.5)

        assert len(events) == 0
        assert len(comp.queue) == 1
        assert comp.busy_workers == 1

    def test_multiple_workers_accept_concurrent_requests(self):
        comp = Component(component_id="svc", service_time=1.0, workers=3)
        for i in range(3):
            events = comp.handle_arrival(Request(id=i, arrival_time=0.0), current_time=0.0)
            assert len(events) == 1

        assert comp.busy_workers == 3

        events = comp.handle_arrival(Request(id=3, arrival_time=0.0), current_time=0.0)
        assert len(events) == 0
        assert len(comp.queue) == 1


class TestComponentCompletion:
    def test_completion_decrements_busy_workers(self):
        comp = Component(component_id="svc", service_time=1.0, workers=1)
        req = Request(id=0, arrival_time=0.0)
        comp.handle_arrival(req, current_time=0.0)
        assert comp.busy_workers == 1

        comp.handle_completion(req, current_time=1.0)
        assert comp.busy_workers == 0

    def test_completion_drains_queue(self):
        comp = Component(component_id="svc", service_time=1.0, workers=1)
        r0 = Request(id=0, arrival_time=0.0)
        r1 = Request(id=1, arrival_time=0.2)

        comp.handle_arrival(r0, current_time=0.0)
        comp.handle_arrival(r1, current_time=0.2)
        assert len(comp.queue) == 1

        events = comp.handle_completion(r0, current_time=1.0)
        assert len(events) == 1
        assert events[0].request_id == 1
        assert events[0].timestamp == 2.0
        assert len(comp.queue) == 0
        assert comp.busy_workers == 1

    def test_completion_with_empty_queue_returns_empty(self):
        comp = Component(component_id="svc", service_time=1.0, workers=1)
        req = Request(id=0, arrival_time=0.0)
        comp.handle_arrival(req, current_time=0.0)

        events = comp.handle_completion(req, current_time=1.0)
        assert len(events) == 0
        assert comp.busy_workers == 0
