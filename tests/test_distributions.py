import random

from archlab.engine.distributions import constant, exponential, lognormal


class TestConstant:
    def test_always_returns_same_value(self):
        fn = constant(5.0)
        assert fn() == 5.0
        assert fn() == 5.0
        assert fn() == 5.0

    def test_different_values(self):
        fn_a = constant(1.0)
        fn_b = constant(2.0)
        assert fn_a() == 1.0
        assert fn_b() == 2.0


class TestExponential:
    def test_returns_positive_values(self):
        random.seed(42)
        fn = exponential(mean=1.0)
        for _ in range(100):
            assert fn() > 0.0

    def test_mean_converges(self):
        random.seed(42)
        fn = exponential(mean=5.0)
        samples = [fn() for _ in range(10000)]
        avg = sum(samples) / len(samples)
        assert abs(avg - 5.0) < 0.5

    def test_seed_reproducibility(self):
        random.seed(99)
        fn = exponential(mean=2.0)
        first_run = [fn() for _ in range(20)]

        random.seed(99)
        fn = exponential(mean=2.0)
        second_run = [fn() for _ in range(20)]

        assert first_run == second_run


class TestLognormal:
    def test_returns_positive_values(self):
        random.seed(42)
        fn = lognormal(mean=0.0, sigma=1.0)
        for _ in range(100):
            assert fn() > 0.0

    def test_seed_reproducibility(self):
        random.seed(99)
        fn = lognormal(mean=1.0, sigma=0.5)
        first_run = [fn() for _ in range(20)]

        random.seed(99)
        fn = lognormal(mean=1.0, sigma=0.5)
        second_run = [fn() for _ in range(20)]

        assert first_run == second_run
