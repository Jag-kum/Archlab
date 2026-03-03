from dataclasses import dataclass, field
from enum import Enum


class EventType(Enum):
    ARRIVAL = "ARRIVAL"
    PROCESS_COMPLETE = "PROCESS_COMPLETE"


_event_counter: int = 0


def _next_sequence() -> int:
    global _event_counter
    _event_counter += 1
    return _event_counter


@dataclass
class Event:
    timestamp: float
    event_type: EventType
    request_id: int
    component_id: str
    service_duration: float = field(default=0.0, repr=False)
    sequence: int = field(default_factory=_next_sequence, repr=False)

    def __lt__(self, other: "Event") -> bool:
        if self.timestamp != other.timestamp:
            return self.timestamp < other.timestamp
        return self.sequence < other.sequence
