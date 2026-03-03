import random
from typing import Callable


def constant(value: float) -> Callable[[], float]:
    def sample() -> float:
        return value
    return sample


def exponential(mean: float) -> Callable[[], float]:
    rate = 1.0 / mean

    def sample() -> float:
        return random.expovariate(rate)
    return sample


def lognormal(mean: float, sigma: float) -> Callable[[], float]:
    def sample() -> float:
        return random.lognormvariate(mean, sigma)
    return sample
