import random

from archlab.engine.component import Component, _normalize_routing, resolve_next_component
from archlab.engine.simulation import SimulationEngine


class TestNormalizeRouting:
    def test_none_stays_none(self):
        assert _normalize_routing(None) is None

    def test_string_becomes_single_entry(self):
        result = _normalize_routing("db")
        assert result == [("db", 1.0)]

    def test_list_passes_through(self):
        routes = [("cache", 0.8), ("db", 0.2)]
        assert _normalize_routing(routes) == routes


class TestResolveNextComponent:
    def test_none_returns_none(self):
        assert resolve_next_component(None) is None

    def test_single_route_always_returns_target(self):
        routing = [("db", 1.0)]
        for _ in range(20):
            assert resolve_next_component(routing) == "db"

    def test_probabilistic_split_respects_distribution(self):
        random.seed(42)
        routing = [("cache", 0.8), ("db", 0.2)]
        results = {"cache": 0, "db": 0}
        trials = 10000
        for _ in range(trials):
            target = resolve_next_component(routing)
            results[target] += 1

        cache_ratio = results["cache"] / trials
        assert 0.75 < cache_ratio < 0.85

    def test_three_way_split(self):
        random.seed(42)
        routing = [("a", 0.5), ("b", 0.3), ("c", 0.2)]
        results = {"a": 0, "b": 0, "c": 0}
        trials = 10000
        for _ in range(trials):
            target = resolve_next_component(routing)
            results[target] += 1

        assert 0.45 < results["a"] / trials < 0.55
        assert 0.25 < results["b"] / trials < 0.35
        assert 0.15 < results["c"] / trials < 0.25


class TestBranchingSimulation:
    def test_cache_hit_miss_pattern(self):
        app = Component(
            component_id="app", service_time=0.1, workers=10,
            next_component=[("cache", 0.8), ("db", 0.2)],
        )
        cache = Component(component_id="cache", service_time=0.05, workers=10)
        db = Component(component_id="db", service_time=0.5, workers=10)

        engine = SimulationEngine(
            components=[app, cache, db],
            entry_component_id="app",
            rps=10,
            duration=10,
            seed=42,
            stochastic=True,
        )
        engine.run()

        cache_count = engine.metrics.component_processed.get("cache", 0)
        db_count = engine.metrics.component_processed.get("db", 0)
        total = cache_count + db_count

        assert total > 0
        cache_ratio = cache_count / total
        assert 0.65 < cache_ratio < 0.95

    def test_string_routing_backward_compat(self):
        fe = Component(component_id="fe", service_time=0.25, workers=10, next_component="be")
        be = Component(component_id="be", service_time=0.25, workers=10)

        engine = SimulationEngine(
            components=[fe, be], entry_component_id="fe", rps=2, duration=4,
        )
        engine.run()

        assert engine.metrics.generated_requests == 8
        assert engine.metrics.completed_requests == 8

    def test_none_routing_is_terminal(self):
        comp = Component(component_id="app", service_time=0.25, workers=10, next_component=None)
        engine = SimulationEngine(
            components=[comp], entry_component_id="app", rps=2, duration=4,
        )
        engine.run()

        assert engine.metrics.completed_requests == 8

    def test_diamond_topology(self):
        entry = Component(
            component_id="entry", service_time=0.1, workers=10,
            next_component=[("left", 0.5), ("right", 0.5)],
        )
        left = Component(component_id="left", service_time=0.1, workers=10, next_component="merge")
        right = Component(component_id="right", service_time=0.1, workers=10, next_component="merge")
        merge = Component(component_id="merge", service_time=0.1, workers=10)

        engine = SimulationEngine(
            components=[entry, left, right, merge],
            entry_component_id="entry",
            rps=10,
            duration=10,
            seed=42,
            stochastic=True,
        )
        engine.run()

        left_count = engine.metrics.component_processed.get("left", 0)
        right_count = engine.metrics.component_processed.get("right", 0)
        merge_count = engine.metrics.component_processed.get("merge", 0)

        assert left_count > 0
        assert right_count > 0
        assert merge_count > 0
        assert abs(left_count - right_count) < 30
