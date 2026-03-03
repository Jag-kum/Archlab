import random

from archlab.engine.component import Component
from archlab.engine.distributions import exponential
from archlab.engine.event import EventType
from archlab.engine.request import Request
from archlab.engine.simulation import SimulationEngine


class TestComponentWithCallableServiceTime:
    def test_callable_produces_varying_durations(self):
        random.seed(42)
        fn = exponential(mean=1.0)
        comp = Component(component_id="svc", service_time=fn, workers=10)

        durations = []
        for i in range(10):
            events = comp.handle_arrival(Request(id=i, arrival_time=0.0), current_time=0.0)
            durations.append(events[0].service_duration)

        assert len(set(durations)) > 1

    def test_float_service_time_still_works(self):
        comp = Component(component_id="svc", service_time=2.0, workers=1)
        req = Request(id=0, arrival_time=0.0)
        events = comp.handle_arrival(req, current_time=0.0)

        assert len(events) == 1
        assert events[0].timestamp == 2.0
        assert events[0].service_duration == 2.0

    def test_event_carries_service_duration(self):
        random.seed(42)
        fn = exponential(mean=1.0)
        comp = Component(component_id="svc", service_time=fn, workers=1)
        req = Request(id=0, arrival_time=0.0)
        events = comp.handle_arrival(req, current_time=0.0)

        assert events[0].service_duration > 0.0
        assert events[0].timestamp == events[0].service_duration


class TestStochasticArrivals:
    def test_stochastic_arrivals_are_not_evenly_spaced(self):
        engine = SimulationEngine(
            components=[Component(component_id="app", service_time=0.1, workers=10)],
            entry_component_id="app",
            rps=10,
            duration=10,
            seed=42,
            stochastic=True,
        )
        engine.initialize_arrivals()

        times = sorted(r.arrival_time for r in engine.requests.values())
        intervals = [times[i + 1] - times[i] for i in range(len(times) - 1)]
        assert len(set(intervals)) > 1

    def test_stochastic_arrivals_stay_within_duration(self):
        engine = SimulationEngine(
            components=[Component(component_id="app", service_time=0.1, workers=10)],
            entry_component_id="app",
            rps=10,
            duration=5,
            seed=42,
            stochastic=True,
        )
        engine.initialize_arrivals()

        for req in engine.requests.values():
            assert req.arrival_time < engine.duration

    def test_deterministic_mode_unchanged(self):
        engine = SimulationEngine(
            components=[Component(component_id="app", service_time=1.0, workers=1)],
            entry_component_id="app",
            rps=2,
            duration=3,
        )
        engine.initialize_arrivals()

        expected = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
        actual = [engine.requests[i].arrival_time for i in range(6)]
        assert actual == expected


class TestSeededSimulation:
    def test_seeded_runs_are_reproducible(self):
        def run_once(seed):
            comp = Component(component_id="app", service_time=exponential(mean=1.0), workers=3)
            engine = SimulationEngine(
                components=[comp],
                entry_component_id="app",
                rps=5,
                duration=20,
                seed=seed,
                stochastic=True,
            )
            engine.run()
            return engine.metrics.summary()

        s1 = run_once(seed=123)
        s2 = run_once(seed=123)

        assert s1["generated"] == s2["generated"]
        assert s1["completed"] == s2["completed"]
        assert s1["average_latency"] == s2["average_latency"]
        assert s1["p95_latency"] == s2["p95_latency"]

    def test_different_seeds_give_different_results(self):
        def run_once(seed):
            comp = Component(component_id="app", service_time=exponential(mean=1.0), workers=3)
            engine = SimulationEngine(
                components=[comp],
                entry_component_id="app",
                rps=5,
                duration=20,
                seed=seed,
                stochastic=True,
            )
            engine.run()
            return engine.metrics.summary()

        s1 = run_once(seed=100)
        s2 = run_once(seed=200)

        assert s1["generated"] != s2["generated"] or s1["average_latency"] != s2["average_latency"]

    def test_stochastic_average_arrival_rate_converges(self):
        comp = Component(component_id="app", service_time=0.01, workers=1000)
        engine = SimulationEngine(
            components=[comp],
            entry_component_id="app",
            rps=100,
            duration=100,
            seed=42,
            stochastic=True,
        )
        engine.run()

        actual_rate = engine.metrics.generated_requests / engine.duration
        assert abs(actual_rate - 100) < 15

    def test_stochastic_with_constant_service_time(self):
        comp = Component(component_id="app", service_time=0.5, workers=10)
        engine = SimulationEngine(
            components=[comp],
            entry_component_id="app",
            rps=5,
            duration=10,
            seed=42,
            stochastic=True,
        )
        engine.run()

        assert engine.metrics.generated_requests > 0
        assert engine.metrics.completed_requests > 0

    def test_full_stochastic_pipeline(self):
        fe = Component(
            component_id="fe",
            service_time=exponential(mean=0.2),
            workers=5,
            next_component="be",
        )
        be = Component(
            component_id="be",
            service_time=exponential(mean=0.5),
            workers=3,
        )
        engine = SimulationEngine(
            components=[fe, be],
            entry_component_id="fe",
            rps=5,
            duration=20,
            seed=42,
            stochastic=True,
        )
        engine.run()

        s = engine.metrics.summary()
        assert s["generated"] > 0
        assert s["completed"] > 0
        assert "fe" in s["component_utilization"]
        assert "be" in s["component_utilization"]
        assert s["average_latency"] > 0
