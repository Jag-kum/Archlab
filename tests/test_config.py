import os
import tempfile

import pytest
import yaml

from archlab.cli.config import build_engine, load_config
from archlab.engine.component import BoundedQueueComponent, Component, LoadBalancer


def _write_yaml(data):
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    yaml.dump(data, f)
    f.close()
    return f.name


class TestLoadConfig:
    def test_loads_yaml_file(self):
        data = {"components": [], "simulation": {"entry": "a", "rps": 1, "duration": 1}}
        path = _write_yaml(data)
        try:
            result = load_config(path)
            assert result["simulation"]["rps"] == 1
        finally:
            os.unlink(path)


class TestBuildEngine:
    def test_simple_component(self):
        config = {
            "components": [
                {"id": "app", "type": "component", "service_time": 1.0, "workers": 2}
            ],
            "simulation": {"entry": "app", "rps": 5, "duration": 10},
        }
        engine = build_engine(config)
        assert "app" in engine.components
        assert isinstance(engine.components["app"], Component)
        assert engine.rps == 5
        assert engine.duration == 10

    def test_bounded_queue_component(self):
        config = {
            "components": [
                {
                    "id": "api",
                    "type": "bounded_queue",
                    "service_time": 0.5,
                    "workers": 3,
                    "max_queue_size": 10,
                }
            ],
            "simulation": {"entry": "api", "rps": 5, "duration": 10},
        }
        engine = build_engine(config)
        comp = engine.components["api"]
        assert isinstance(comp, BoundedQueueComponent)
        assert comp.max_queue_size == 10

    def test_load_balancer(self):
        config = {
            "components": [
                {"id": "lb", "type": "load_balancer", "targets": ["a", "b"]},
                {"id": "a", "type": "component", "service_time": 1.0, "workers": 1},
                {"id": "b", "type": "component", "service_time": 1.0, "workers": 1},
            ],
            "simulation": {"entry": "lb", "rps": 2, "duration": 5},
        }
        engine = build_engine(config)
        assert isinstance(engine.components["lb"], LoadBalancer)

    def test_exponential_service_time(self):
        config = {
            "components": [
                {
                    "id": "app",
                    "type": "component",
                    "service_time": {"distribution": "exponential", "mean": 2.0},
                    "workers": 1,
                }
            ],
            "simulation": {"entry": "app", "rps": 1, "duration": 5, "seed": 42, "stochastic": True},
        }
        engine = build_engine(config)
        engine.run()
        assert engine.metrics.generated_requests > 0

    def test_lognormal_service_time(self):
        config = {
            "components": [
                {
                    "id": "app",
                    "type": "component",
                    "service_time": {"distribution": "lognormal", "mean": 0.0, "sigma": 0.5},
                    "workers": 5,
                }
            ],
            "simulation": {"entry": "app", "rps": 5, "duration": 10, "seed": 42, "stochastic": True},
        }
        engine = build_engine(config)
        engine.run()
        assert engine.metrics.completed_requests > 0

    def test_probabilistic_routing(self):
        config = {
            "components": [
                {
                    "id": "app",
                    "type": "component",
                    "service_time": 0.1,
                    "workers": 10,
                    "next_component": [
                        {"target": "cache", "probability": 0.8},
                        {"target": "db", "probability": 0.2},
                    ],
                },
                {"id": "cache", "type": "component", "service_time": 0.05, "workers": 10},
                {"id": "db", "type": "component", "service_time": 0.5, "workers": 10},
            ],
            "simulation": {"entry": "app", "rps": 10, "duration": 5, "seed": 42, "stochastic": True},
        }
        engine = build_engine(config)
        engine.run()
        assert engine.metrics.component_processed.get("cache", 0) > 0
        assert engine.metrics.component_processed.get("db", 0) > 0

    def test_string_next_component(self):
        config = {
            "components": [
                {"id": "fe", "type": "component", "service_time": 0.5, "workers": 5, "next_component": "be"},
                {"id": "be", "type": "component", "service_time": 0.5, "workers": 5},
            ],
            "simulation": {"entry": "fe", "rps": 2, "duration": 5},
        }
        engine = build_engine(config)
        engine.run()
        assert engine.metrics.completed_requests > 0

    def test_stochastic_and_seed(self):
        config = {
            "components": [
                {"id": "app", "type": "component", "service_time": 1.0, "workers": 5}
            ],
            "simulation": {"entry": "app", "rps": 5, "duration": 10, "seed": 99, "stochastic": True},
        }
        engine = build_engine(config)
        assert engine.seed == 99
        assert engine.stochastic is True

    def test_unknown_type_raises(self):
        config = {
            "components": [{"id": "x", "type": "unknown", "service_time": 1.0, "workers": 1}],
            "simulation": {"entry": "x", "rps": 1, "duration": 1},
        }
        with pytest.raises(ValueError, match="Unknown component type"):
            build_engine(config)


class TestFullYamlRoundTrip:
    def test_yaml_file_produces_results(self):
        config = {
            "components": [
                {"id": "app", "type": "component", "service_time": 0.5, "workers": 3}
            ],
            "simulation": {"entry": "app", "rps": 4, "duration": 5},
        }
        path = _write_yaml(config)
        try:
            loaded = load_config(path)
            engine = build_engine(loaded)
            engine.run()
            s = engine.metrics.summary()
            assert s["generated"] == 20
            assert s["completed"] > 0
        finally:
            os.unlink(path)
