"""Tests for the benchmark validation module.

These tests verify the comparison logic and ArchLab simulation side
without requiring live Flask servers (which would be slow/flaky in CI).
"""
import pytest

from benchmark.validate import compare_results, run_archlab_simulation


class TestCompareResults:
    def test_identical_results_pass(self):
        real = {"throughput": 5.0, "p95_latency": 1.0, "average_latency": 0.5,
                "generated": 100, "completed": 100, "dropped": 0}
        sim = {"throughput": 5.0, "p95_latency": 1.0, "average_latency": 0.5,
               "generated": 100, "completed": 100, "dropped": 0}
        result = compare_results(real, sim)
        assert result["all_within_tolerance"] is True

    def test_within_tolerance_passes(self):
        real = {"throughput": 5.0, "p95_latency": 1.0, "average_latency": 0.5,
                "generated": 100, "completed": 95, "dropped": 5}
        sim = {"throughput": 5.5, "p95_latency": 1.1, "average_latency": 0.55,
               "generated": 100, "completed": 90, "dropped": 10}
        result = compare_results(real, sim, tolerance=0.25)
        assert result["all_within_tolerance"] is True

    def test_outside_tolerance_fails(self):
        real = {"throughput": 5.0, "p95_latency": 1.0, "average_latency": 0.5,
                "generated": 100, "completed": 100, "dropped": 0}
        sim = {"throughput": 10.0, "p95_latency": 3.0, "average_latency": 2.0,
               "generated": 100, "completed": 100, "dropped": 0}
        result = compare_results(real, sim, tolerance=0.25)
        assert result["all_within_tolerance"] is False

    def test_completion_rate_check(self):
        real = {"throughput": 5.0, "p95_latency": 1.0, "average_latency": 0.5,
                "generated": 100, "completed": 100, "dropped": 0}
        sim = {"throughput": 5.0, "p95_latency": 1.0, "average_latency": 0.5,
               "generated": 100, "completed": 50, "dropped": 50}
        result = compare_results(real, sim, tolerance=0.25)
        assert result["completion_rate"]["within_tolerance"] is False

    def test_zero_real_values(self):
        real = {"throughput": 0, "p95_latency": 0, "average_latency": 0,
                "generated": 0, "completed": 0, "dropped": 0}
        sim = {"throughput": 0, "p95_latency": 0, "average_latency": 0,
               "generated": 0, "completed": 0, "dropped": 0}
        result = compare_results(real, sim)
        assert result["all_within_tolerance"] is True

    def test_includes_error_percentage(self):
        real = {"throughput": 10.0, "p95_latency": 2.0, "average_latency": 1.0,
                "generated": 100, "completed": 80, "dropped": 20}
        sim = {"throughput": 8.0, "p95_latency": 2.4, "average_latency": 1.2,
               "generated": 100, "completed": 80, "dropped": 20}
        result = compare_results(real, sim)
        assert result["throughput"]["error_pct"] == 20.0
        assert result["p95_latency"]["error_pct"] == 20.0

    def test_tight_tolerance(self):
        real = {"throughput": 5.0, "p95_latency": 1.0, "average_latency": 0.5,
                "generated": 100, "completed": 100, "dropped": 0}
        sim = {"throughput": 5.3, "p95_latency": 1.1, "average_latency": 0.55,
               "generated": 100, "completed": 100, "dropped": 0}
        result_tight = compare_results(real, sim, tolerance=0.05)
        result_loose = compare_results(real, sim, tolerance=0.25)
        assert result_tight["all_within_tolerance"] is False
        assert result_loose["all_within_tolerance"] is True


class TestArchLabSimulation:
    def test_produces_expected_keys(self):
        result = run_archlab_simulation(
            api_mean_st=0.1, db_mean_st=0.3,
            api_workers=4, db_workers=4,
            rps=5, duration=10, seeds=[42],
        )
        assert "throughput" in result
        assert "p95_latency" in result
        assert "average_latency" in result
        assert "generated" in result
        assert "completed" in result

    def test_multi_seed_averages(self):
        single = run_archlab_simulation(
            api_mean_st=0.1, db_mean_st=0.3,
            api_workers=4, db_workers=4,
            rps=5, duration=10, seeds=[42],
        )
        multi = run_archlab_simulation(
            api_mean_st=0.1, db_mean_st=0.3,
            api_workers=4, db_workers=4,
            rps=5, duration=10, seeds=[42, 100, 200],
        )
        assert isinstance(multi["throughput"], float)
        assert isinstance(multi["generated"], float)

    def test_more_workers_improves_throughput(self):
        low = run_archlab_simulation(
            api_mean_st=0.1, db_mean_st=0.5,
            api_workers=1, db_workers=1,
            rps=10, duration=10, seeds=[42],
        )
        high = run_archlab_simulation(
            api_mean_st=0.1, db_mean_st=0.5,
            api_workers=5, db_workers=5,
            rps=10, duration=10, seeds=[42],
        )
        assert high["completed"] >= low["completed"]

    def test_identifies_bottleneck(self):
        result = run_archlab_simulation(
            api_mean_st=0.01, db_mean_st=1.0,
            api_workers=10, db_workers=1,
            rps=5, duration=10, seeds=[42],
        )
        assert result["bottleneck"] == "db"
