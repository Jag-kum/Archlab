from archlab.engine.component import Component, LoadBalancer
from archlab.engine.event import EventType
from archlab.engine.request import Request
from archlab.engine.simulation import SimulationEngine


class TestLoadBalancerRouting:
    def test_routes_to_first_target(self):
        lb = LoadBalancer(component_id="lb", targets=["a", "b"])
        req = Request(id=0, arrival_time=0.0)
        events = lb.handle_arrival(req, current_time=0.0)

        assert len(events) == 1
        assert events[0].event_type == EventType.ARRIVAL
        assert events[0].component_id == "a"
        assert events[0].timestamp == 0.0

    def test_round_robin_distribution(self):
        lb = LoadBalancer(component_id="lb", targets=["a", "b", "c"])
        targets_hit = []
        for i in range(6):
            events = lb.handle_arrival(Request(id=i, arrival_time=0.0), current_time=0.0)
            targets_hit.append(events[0].component_id)

        assert targets_hit == ["a", "b", "c", "a", "b", "c"]

    def test_single_target(self):
        lb = LoadBalancer(component_id="lb", targets=["only"])
        targets_hit = []
        for i in range(3):
            events = lb.handle_arrival(Request(id=i, arrival_time=0.0), current_time=0.0)
            targets_hit.append(events[0].component_id)

        assert targets_hit == ["only", "only", "only"]

    def test_completion_returns_empty(self):
        lb = LoadBalancer(component_id="lb", targets=["a", "b"])
        events = lb.handle_completion(Request(id=0, arrival_time=0.0), current_time=1.0)
        assert events == []

    def test_no_busy_workers_tracked(self):
        lb = LoadBalancer(component_id="lb", targets=["a", "b"])
        lb.handle_arrival(Request(id=0, arrival_time=0.0), current_time=0.0)
        assert lb.busy_workers == 0


class TestLoadBalancerIntegration:
    def test_lb_distributes_across_workers(self):
        lb = LoadBalancer(component_id="lb", targets=["w1", "w2"])
        w1 = Component(component_id="w1", service_time=0.1, workers=5)
        w2 = Component(component_id="w2", service_time=0.1, workers=5)

        engine = SimulationEngine(
            components=[lb, w1, w2],
            entry_component_id="lb",
            rps=4,
            duration=5,
        )
        engine.run()

        assert engine.metrics.generated_requests == 20
        assert engine.metrics.completed_requests == 20

        w1_processed = engine.metrics.component_processed.get("w1", 0)
        w2_processed = engine.metrics.component_processed.get("w2", 0)
        assert w1_processed == 10
        assert w2_processed == 10

    def test_lb_with_uneven_backends(self):
        lb = LoadBalancer(component_id="lb", targets=["fast", "slow"])
        fast = Component(component_id="fast", service_time=0.1, workers=10)
        slow = Component(component_id="slow", service_time=2.0, workers=1)

        engine = SimulationEngine(
            components=[lb, fast, slow],
            entry_component_id="lb",
            rps=2,
            duration=5,
        )
        engine.run()

        assert engine.metrics.generated_requests == 10
        fast_processed = engine.metrics.component_processed.get("fast", 0)
        slow_processed = engine.metrics.component_processed.get("slow", 0)
        assert fast_processed == 5
        assert slow_processed > 0
        assert slow_processed <= 5

    def test_lb_three_way_split(self):
        lb = LoadBalancer(component_id="lb", targets=["a", "b", "c"])
        a = Component(component_id="a", service_time=0.25, workers=10)
        b = Component(component_id="b", service_time=0.25, workers=10)
        c = Component(component_id="c", service_time=0.25, workers=10)

        engine = SimulationEngine(
            components=[lb, a, b, c],
            entry_component_id="lb",
            rps=3,
            duration=4,
        )
        engine.run()

        assert engine.metrics.generated_requests == 12
        assert engine.metrics.completed_requests == 12
        assert engine.metrics.component_processed["a"] == 4
        assert engine.metrics.component_processed["b"] == 4
        assert engine.metrics.component_processed["c"] == 4
