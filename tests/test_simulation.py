from archlab.engine.component import Component
from archlab.engine.event import EventType
from archlab.engine.simulation import SimulationEngine


class TestInitializeArrivals:
    def test_generates_correct_number_of_requests(self):
        comp = Component(component_id="app", service_time=1.0, workers=1)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=2, duration=3,
        )
        engine.initialize_arrivals()
        assert len(engine.requests) == 6
        assert engine.metrics.generated_requests == 6

    def test_timestamps_are_deterministic(self):
        comp = Component(component_id="app", service_time=1.0, workers=1)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=2, duration=3,
        )
        engine.initialize_arrivals()
        expected = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
        actual = [engine.requests[i].arrival_time for i in range(6)]
        assert actual == expected

    def test_no_float_drift(self):
        comp = Component(component_id="app", service_time=1.0, workers=1)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=3, duration=100,
        )
        engine.initialize_arrivals()
        last_id = len(engine.requests) - 1
        last_req = engine.requests[last_id]
        expected = last_id * (1.0 / 3)
        assert last_req.arrival_time == expected

    def test_all_events_are_arrivals(self):
        comp = Component(component_id="app", service_time=1.0, workers=1)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=2, duration=3,
        )
        engine.initialize_arrivals()
        for event in engine.event_queue:
            assert event.event_type == EventType.ARRIVAL


class TestRun:
    def test_single_component_basic(self):
        comp = Component(component_id="app", service_time=1.0, workers=1)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=1, duration=3,
        )
        engine.run()

        assert engine.metrics.generated_requests == 3
        assert engine.metrics.completed_requests == 3
        assert engine.metrics.latencies == [1.0, 1.0, 1.0]

    def test_saturated_single_worker(self):
        comp = Component(component_id="app", service_time=1.0, workers=1)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=2, duration=3,
        )
        engine.run()

        assert engine.metrics.generated_requests == 6
        assert engine.metrics.completed_requests > 0
        assert engine.metrics.completed_requests < engine.metrics.generated_requests
        for i in range(1, len(engine.metrics.latencies)):
            assert engine.metrics.latencies[i] >= engine.metrics.latencies[i - 1]

    def test_enough_workers_no_queueing(self):
        comp = Component(component_id="app", service_time=0.25, workers=10)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=2, duration=4,
        )
        engine.run()

        assert engine.metrics.generated_requests == 8
        assert engine.metrics.completed_requests == 8
        assert all(lat == 0.25 for lat in engine.metrics.latencies)

    def test_chained_components(self):
        frontend = Component(component_id="fe", service_time=0.5, workers=10, next_component="be")
        backend = Component(component_id="be", service_time=0.5, workers=10)
        engine = SimulationEngine(
            components=[frontend, backend], entry_component_id="fe", rps=1, duration=2,
        )
        engine.run()

        assert engine.metrics.generated_requests == 2
        assert engine.metrics.completed_requests == 2
        assert all(lat == 1.0 for lat in engine.metrics.latencies)

    def test_busy_time_recorded(self):
        comp = Component(component_id="app", service_time=0.5, workers=10)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=2, duration=3,
        )
        engine.run()

        assert "app" in engine.metrics.component_busy_time
        assert engine.metrics.component_busy_time["app"] == 3.0

    def test_processed_count_recorded(self):
        comp = Component(component_id="app", service_time=0.5, workers=10)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=2, duration=3,
        )
        engine.run()

        assert engine.metrics.component_processed["app"] == 6


class TestReset:
    def test_reset_clears_state(self):
        comp = Component(component_id="app", service_time=1.0, workers=1)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=2, duration=3,
        )
        engine.run()
        assert engine.metrics.generated_requests > 0

        engine.reset()
        assert engine.current_time == 0.0
        assert len(engine.event_queue) == 0
        assert len(engine.requests) == 0
        assert engine.metrics.generated_requests == 0
        assert comp.busy_workers == 0
        assert len(comp.queue) == 0

    def test_run_after_reset_produces_same_results(self):
        comp = Component(component_id="app", service_time=1.0, workers=10)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=2, duration=3,
        )
        engine.run()
        first_summary = engine.metrics.summary()

        engine.reset()
        engine.run()
        second_summary = engine.metrics.summary()

        assert first_summary["generated"] == second_summary["generated"]
        assert first_summary["completed"] == second_summary["completed"]
        assert first_summary["average_latency"] == second_summary["average_latency"]


class TestSummaryIntegration:
    def test_summary_output_structure(self):
        comp = Component(component_id="app", service_time=1.0, workers=10)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=2, duration=3,
        )
        engine.run()
        s = engine.metrics.summary()

        assert "generated" in s
        assert "completed" in s
        assert "dropped" in s
        assert "average_latency" in s
        assert "p95_latency" in s
        assert "throughput" in s
        assert "component_utilization" in s

    def test_no_drops_when_capacity_sufficient(self):
        comp = Component(component_id="app", service_time=0.1, workers=10)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=5, duration=2,
        )
        engine.run()
        s = engine.metrics.summary()
        assert s["dropped"] == 0

    def test_zero_duration_produces_empty_results(self):
        comp = Component(component_id="app", service_time=1.0, workers=1)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=1, duration=0,
        )
        engine.run()
        s = engine.metrics.summary()
        assert s["generated"] == 0
        assert s["completed"] == 0
