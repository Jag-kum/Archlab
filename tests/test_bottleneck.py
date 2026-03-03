from archlab.engine.component import Component
from archlab.engine.distributions import exponential
from archlab.engine.metrics import MetricsCollector
from archlab.engine.simulation import SimulationEngine


class TestBottleneckDetection:
    def test_identifies_saturated_component(self):
        fast = Component(component_id="fast", service_time=0.1, workers=10, next_component="slow")
        slow = Component(component_id="slow", service_time=2.0, workers=1)

        engine = SimulationEngine(
            components=[fast, slow], entry_component_id="fast", rps=2, duration=5,
        )
        engine.run()
        s = engine.metrics.summary()

        assert s["bottleneck"] == "slow"

    def test_no_bottleneck_when_empty(self):
        m = MetricsCollector(simulation_duration=10.0)
        s = m.summary()
        assert s["bottleneck"] is None

    def test_single_component_is_bottleneck(self):
        comp = Component(component_id="app", service_time=1.0, workers=1)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=2, duration=5,
        )
        engine.run()
        s = engine.metrics.summary()
        assert s["bottleneck"] == "app"

    def test_bottleneck_considers_worker_count(self):
        a = Component(component_id="a", service_time=0.5, workers=10, next_component="b")
        b = Component(component_id="b", service_time=0.5, workers=1)

        engine = SimulationEngine(
            components=[a, b], entry_component_id="a", rps=2, duration=10,
        )
        engine.run()
        s = engine.metrics.summary()

        assert s["bottleneck"] == "b"


class TestSLAChecking:
    def test_sla_passes_when_within_limits(self):
        comp = Component(component_id="app", service_time=0.25, workers=10)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=2, duration=4,
        )
        engine.run()

        sla = {"max_p95_latency": 1.0, "min_throughput": 1.0, "max_drop_rate": 0.1}
        s = engine.metrics.summary(sla=sla)

        assert s["sla"]["all_passed"] is True
        assert s["sla"]["max_p95_latency"]["passed"] is True
        assert s["sla"]["min_throughput"]["passed"] is True
        assert s["sla"]["max_drop_rate"]["passed"] is True

    def test_sla_fails_on_high_latency(self):
        comp = Component(component_id="app", service_time=1.0, workers=1)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=3, duration=5,
        )
        engine.run()

        sla = {"max_p95_latency": 0.5}
        s = engine.metrics.summary(sla=sla)

        assert s["sla"]["max_p95_latency"]["passed"] is False
        assert s["sla"]["all_passed"] is False

    def test_sla_fails_on_low_throughput(self):
        comp = Component(component_id="app", service_time=1.0, workers=1)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=2, duration=5,
        )
        engine.run()

        sla = {"min_throughput": 5.0}
        s = engine.metrics.summary(sla=sla)

        assert s["sla"]["min_throughput"]["passed"] is False

    def test_sla_fails_on_high_drop_rate(self):
        comp = Component(component_id="app", service_time=1.0, workers=1)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=5, duration=5,
        )
        engine.run()

        sla = {"max_drop_rate": 0.01}
        s = engine.metrics.summary(sla=sla)

        assert s["sla"]["max_drop_rate"]["passed"] is False

    def test_sla_p99_check(self):
        comp = Component(component_id="app", service_time=0.25, workers=10)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=2, duration=4,
        )
        engine.run()

        sla = {"max_p99_latency": 1.0}
        s = engine.metrics.summary(sla=sla)

        assert s["sla"]["max_p99_latency"]["passed"] is True

    def test_no_sla_key_when_not_provided(self):
        comp = Component(component_id="app", service_time=1.0, workers=1)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=1, duration=3,
        )
        engine.run()
        s = engine.metrics.summary()
        assert "sla" not in s

    def test_sla_includes_actual_values(self):
        comp = Component(component_id="app", service_time=0.25, workers=10)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=2, duration=4,
        )
        engine.run()

        sla = {"max_p95_latency": 5.0}
        s = engine.metrics.summary(sla=sla)

        check = s["sla"]["max_p95_latency"]
        assert "threshold" in check
        assert "actual" in check
        assert "passed" in check
