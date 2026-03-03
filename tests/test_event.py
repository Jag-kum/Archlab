import heapq

from archlab.engine.event import Event, EventType


class TestEventOrdering:
    def test_earlier_event_is_less_than_later(self):
        e1 = Event(timestamp=1.0, event_type=EventType.ARRIVAL, request_id=0, component_id="a")
        e2 = Event(timestamp=2.0, event_type=EventType.ARRIVAL, request_id=1, component_id="a")
        assert e1 < e2

    def test_later_event_is_not_less_than_earlier(self):
        e1 = Event(timestamp=2.0, event_type=EventType.ARRIVAL, request_id=0, component_id="a")
        e2 = Event(timestamp=1.0, event_type=EventType.ARRIVAL, request_id=1, component_id="a")
        assert not (e1 < e2)

    def test_same_timestamp_uses_sequence_tiebreaker(self):
        e1 = Event(timestamp=1.0, event_type=EventType.ARRIVAL, request_id=0, component_id="a")
        e2 = Event(timestamp=1.0, event_type=EventType.PROCESS_COMPLETE, request_id=1, component_id="a")
        assert e1 < e2  # e1 created first, lower sequence

    def test_heap_ordering_with_same_timestamps(self):
        events = [
            Event(timestamp=1.0, event_type=EventType.PROCESS_COMPLETE, request_id=2, component_id="a"),
            Event(timestamp=1.0, event_type=EventType.ARRIVAL, request_id=0, component_id="a"),
            Event(timestamp=1.0, event_type=EventType.ARRIVAL, request_id=1, component_id="a"),
        ]
        heapq.heapify(events)
        ordered = [heapq.heappop(events) for _ in range(3)]
        assert ordered[0].request_id == 2
        assert ordered[1].request_id == 0
        assert ordered[2].request_id == 1

    def test_heap_ordering_by_timestamp(self):
        events = [
            Event(timestamp=3.0, event_type=EventType.ARRIVAL, request_id=2, component_id="a"),
            Event(timestamp=1.0, event_type=EventType.ARRIVAL, request_id=0, component_id="a"),
            Event(timestamp=2.0, event_type=EventType.ARRIVAL, request_id=1, component_id="a"),
        ]
        heapq.heapify(events)
        ordered = [heapq.heappop(events) for _ in range(3)]
        assert ordered[0].timestamp == 1.0
        assert ordered[1].timestamp == 2.0
        assert ordered[2].timestamp == 3.0
