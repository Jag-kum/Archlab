import pytest
from fastapi.testclient import TestClient

from archlab.api.app import app

client = TestClient(app)


def _simple_config(workers=2, rps=5, duration=5):
    return {
        "components": [
            {"id": "app", "type": "component", "service_time": 0.5, "workers": workers}
        ],
        "simulation": {"entry": "app", "rps": rps, "duration": duration},
    }


def _chain_config():
    return {
        "components": [
            {
                "id": "api",
                "type": "component",
                "service_time": {"distribution": "exponential", "mean": 0.2},
                "workers": 5,
                "next_component": "db",
            },
            {
                "id": "db",
                "type": "component",
                "service_time": {"distribution": "exponential", "mean": 0.5},
                "workers": 2,
            },
        ],
        "simulation": {
            "entry": "api",
            "rps": 5,
            "duration": 10,
            "seed": 42,
            "stochastic": True,
        },
    }


class TestSimulateEndpoint:
    def test_basic_simulate(self):
        resp = client.post("/simulate", json=_simple_config())
        assert resp.status_code == 200
        data = resp.json()
        assert "generated" in data
        assert "completed" in data
        assert "throughput" in data
        assert "bottleneck" in data

    def test_returns_all_metric_keys(self):
        resp = client.post("/simulate", json=_simple_config())
        data = resp.json()
        expected_keys = {
            "generated", "completed", "dropped",
            "average_latency", "p95_latency", "p99_latency",
            "throughput", "component_utilization", "bottleneck",
        }
        assert expected_keys.issubset(data.keys())

    def test_chain_topology(self):
        resp = client.post("/simulate", json=_chain_config())
        assert resp.status_code == 200
        data = resp.json()
        assert "api" in data["component_utilization"]
        assert "db" in data["component_utilization"]

    def test_with_sla(self):
        config = _simple_config()
        config["sla"] = {"max_p95_latency": 10.0, "min_throughput": 1.0}
        resp = client.post("/simulate", json=config)
        assert resp.status_code == 200
        data = resp.json()
        assert "sla" in data
        assert "all_passed" in data["sla"]

    def test_sla_failure(self):
        config = _simple_config(workers=1, rps=20, duration=5)
        config["sla"] = {"max_p95_latency": 0.001}
        resp = client.post("/simulate", json=config)
        data = resp.json()
        assert data["sla"]["max_p95_latency"]["passed"] is False

    def test_bounded_queue_component(self):
        config = {
            "components": [
                {
                    "id": "app",
                    "type": "bounded_queue",
                    "service_time": 1.0,
                    "workers": 1,
                    "max_queue_size": 2,
                }
            ],
            "simulation": {"entry": "app", "rps": 5, "duration": 5},
        }
        resp = client.post("/simulate", json=config)
        assert resp.status_code == 200
        assert resp.json()["dropped"] > 0

    def test_load_balancer(self):
        config = {
            "components": [
                {"id": "lb", "type": "load_balancer", "targets": ["w1", "w2"]},
                {"id": "w1", "type": "component", "service_time": 0.5, "workers": 2},
                {"id": "w2", "type": "component", "service_time": 0.5, "workers": 2},
            ],
            "simulation": {"entry": "lb", "rps": 5, "duration": 5},
        }
        resp = client.post("/simulate", json=config)
        assert resp.status_code == 200
        data = resp.json()
        assert data["completed"] > 0

    def test_seeded_reproducibility(self):
        config = _chain_config()
        r1 = client.post("/simulate", json=config).json()
        r2 = client.post("/simulate", json=config).json()
        assert r1["completed"] == r2["completed"]
        assert r1["average_latency"] == r2["average_latency"]

    def test_invalid_config_returns_error(self):
        resp = client.post("/simulate", json={"bad": "data"})
        assert resp.status_code == 422

    def test_probabilistic_routing(self):
        config = {
            "components": [
                {
                    "id": "app",
                    "type": "component",
                    "service_time": 0.2,
                    "workers": 5,
                    "next_component": [
                        {"target": "cache", "probability": 0.8},
                        {"target": "db", "probability": 0.2},
                    ],
                },
                {"id": "cache", "type": "component", "service_time": 0.1, "workers": 5},
                {"id": "db", "type": "component", "service_time": 0.5, "workers": 2},
            ],
            "simulation": {"entry": "app", "rps": 5, "duration": 5, "seed": 42, "stochastic": True},
        }
        resp = client.post("/simulate", json=config)
        assert resp.status_code == 200
        data = resp.json()
        assert "cache" in data["component_utilization"]
        assert "db" in data["component_utilization"]


class TestSweepEndpoint:
    def test_basic_sweep(self):
        config = _simple_config()
        config["param"] = "app.workers"
        config["values"] = [1, 2, 3]
        resp = client.post("/sweep", json=config)
        assert resp.status_code == 200
        data = resp.json()
        assert data["param"] == "app.workers"
        assert len(data["results"]) == 3

    def test_sweep_param_values_match(self):
        config = _simple_config()
        config["param"] = "app.workers"
        config["values"] = [1, 5, 10]
        resp = client.post("/sweep", json=config)
        data = resp.json()
        values = [r["param_value"] for r in data["results"]]
        assert values == [1, 5, 10]

    def test_sweep_with_seeds(self):
        config = _chain_config()
        config["param"] = "db.workers"
        config["values"] = [1, 3]
        config["seeds"] = [42, 100, 200]
        resp = client.post("/sweep", json=config)
        data = resp.json()
        assert len(data["results"]) == 2
        assert data["results"][0]["runs"] == 3

    def test_sweep_simulation_param(self):
        config = _simple_config(workers=10)
        config["param"] = "simulation.rps"
        config["values"] = [1, 5, 10]
        resp = client.post("/sweep", json=config)
        data = resp.json()
        generated = [r["generated"] for r in data["results"]]
        assert generated[0] < generated[1] < generated[2]

    def test_invalid_sweep_param(self):
        config = _simple_config()
        config["param"] = "nonexistent.field"
        config["values"] = [1, 2]
        resp = client.post("/sweep", json=config)
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"]


class TestFrontendEndpoint:
    def test_index_returns_html(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "ArchLab" in resp.text

    def test_html_contains_tabs(self):
        resp = client.get("/")
        assert "Simulate" in resp.text
        assert "Sweep" in resp.text
