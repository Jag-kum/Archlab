import pytest

from archlab.cli.sweep import (
    _apply_param,
    _find_component_field,
    format_sweep_table,
    run_sweep,
)


def _base_config(workers=2, rps=5, duration=5):
    return {
        "components": [
            {"id": "app", "type": "component", "service_time": 0.5, "workers": workers}
        ],
        "simulation": {"entry": "app", "rps": rps, "duration": duration},
    }


def _chain_config():
    return {
        "components": [
            {"id": "fe", "type": "component", "service_time": 0.1, "workers": 5, "next_component": "db"},
            {"id": "db", "type": "component", "service_time": 0.5, "workers": 2},
        ],
        "simulation": {"entry": "fe", "rps": 5, "duration": 10, "seed": 42, "stochastic": True},
    }


class TestFindComponentField:
    def test_finds_component(self):
        cfg = _base_config()
        target, field = _find_component_field(cfg, "app.workers")
        assert target["id"] == "app"
        assert field == "workers"

    def test_finds_simulation_field(self):
        cfg = _base_config()
        target, field = _find_component_field(cfg, "simulation.rps")
        assert field == "rps"
        assert target["rps"] == 5

    def test_missing_component_raises(self):
        cfg = _base_config()
        with pytest.raises(ValueError, match="not found"):
            _find_component_field(cfg, "missing.workers")

    def test_bad_path_raises(self):
        cfg = _base_config()
        with pytest.raises(ValueError, match="must be"):
            _find_component_field(cfg, "too.many.parts")


class TestApplyParam:
    def test_modifies_copy_not_original(self):
        cfg = _base_config(workers=2)
        modified = _apply_param(cfg, "app.workers", 10)
        assert modified["components"][0]["workers"] == 10
        assert cfg["components"][0]["workers"] == 2

    def test_simulation_param(self):
        cfg = _base_config(rps=5)
        modified = _apply_param(cfg, "simulation.rps", 20)
        assert modified["simulation"]["rps"] == 20
        assert cfg["simulation"]["rps"] == 5


class TestRunSweep:
    def test_returns_one_result_per_value(self):
        cfg = _base_config()
        results = run_sweep(cfg, "app.workers", [1, 2, 3])
        assert len(results) == 3

    def test_each_result_has_param_value(self):
        cfg = _base_config()
        results = run_sweep(cfg, "app.workers", [1, 5, 10])
        values = [r["param_value"] for r in results]
        assert values == [1, 5, 10]

    def test_more_workers_means_more_completions(self):
        cfg = _base_config(rps=10, duration=5)
        results = run_sweep(cfg, "app.workers", [1, 5, 10])
        completions = [r["completed"] for r in results]
        assert completions[-1] >= completions[0]

    def test_sweep_simulation_param(self):
        cfg = _base_config(workers=10)
        results = run_sweep(cfg, "simulation.rps", [1, 5, 10])
        generated = [r["generated"] for r in results]
        assert generated[0] < generated[1] < generated[2]

    def test_multi_seed_averaging(self):
        cfg = _chain_config()
        results = run_sweep(
            cfg, "db.workers", [1, 3],
            seeds=[42, 100, 200],
        )
        assert len(results) == 2
        assert results[0]["runs"] == 3
        assert results[1]["runs"] == 3
        assert isinstance(results[0]["average_latency"], float)
        assert isinstance(results[0]["generated"], float)

    def test_multi_seed_reduces_variance(self):
        cfg = _chain_config()
        results_single = run_sweep(cfg, "db.workers", [2], seeds=[42])
        results_multi = run_sweep(cfg, "db.workers", [2], seeds=[42, 100, 200, 300, 400])
        assert results_single[0]["runs"] == 1
        assert results_multi[0]["runs"] == 5

    def test_sweep_with_sla(self):
        cfg = _base_config(rps=10, duration=5)
        sla = {"max_p95_latency": 1.0}
        results = run_sweep(cfg, "app.workers", [1, 10], sla=sla)
        assert "sla" in results[-1] or "sla_pass_rate" in results[-1]

    def test_bottleneck_in_chain_sweep(self):
        cfg = _chain_config()
        results = run_sweep(cfg, "db.workers", [1, 5])
        for r in results:
            assert "bottleneck" in r


class TestFormatSweepTable:
    def test_produces_readable_output(self):
        cfg = _base_config()
        results = run_sweep(cfg, "app.workers", [1, 2, 3])
        table = format_sweep_table(results, "app.workers")
        assert "app.workers" in table
        assert "Avg Lat" in table
        assert "P95 Lat" in table
        assert "Bottleneck" in table
