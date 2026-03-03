from dataclasses import dataclass
from typing import Optional


@dataclass
class Request:
    id: int
    arrival_time: float
    completion_time: Optional[float] = None
