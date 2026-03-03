from archlab.engine.request import Request


class TestRequest:
    def test_default_completion_time_is_none(self):
        r = Request(id=0, arrival_time=1.0)
        assert r.completion_time is None

    def test_fields_assigned_correctly(self):
        r = Request(id=5, arrival_time=2.5, completion_time=3.0)
        assert r.id == 5
        assert r.arrival_time == 2.5
        assert r.completion_time == 3.0

    def test_completion_time_can_be_set(self):
        r = Request(id=0, arrival_time=0.0)
        r.completion_time = 10.0
        assert r.completion_time == 10.0
