from archlab.engine.metrics import MetricsCollector


class TestRecordGeneration:
    def test_increments_count(self):
        m = MetricsCollector(simulation_duration=10.0)
        m.record_generation()
        m.record_generation()
        assert m.generated_requests == 2


class TestRecordCompletion:
    def test_increments_count_and_stores_latency(self):
        m = MetricsCollector(simulation_duration=10.0)
        m.record_completion(request_id=0, latency=1.5)
        m.record_completion(request_id=1, latency=2.0)
        assert m.completed_requests == 2
        assert m.latencies == [1.5, 2.0]


class TestRecordBusyTime:
    def test_accumulates_per_component(self):
        m = MetricsCollector(simulation_duration=10.0)
        m.record_busy_time("svc", 1.0)
        m.record_busy_time("svc", 2.0)
        m.record_busy_time("db", 0.5)
        assert m.component_busy_time["svc"] == 3.0
        assert m.component_busy_time["db"] == 0.5

    def test_initializes_missing_component(self):
        m = MetricsCollector(simulation_duration=10.0)
        m.record_busy_time("new", 1.0)
        assert "new" in m.component_busy_time


class TestRecordProcessed:
    def test_increments_per_component(self):
        m = MetricsCollector(simulation_duration=10.0)
        m.record_processed("svc")
        m.record_processed("svc")
        m.record_processed("db")
        assert m.component_processed["svc"] == 2
        assert m.component_processed["db"] == 1


class TestSummary:
    def test_empty_simulation(self):
        m = MetricsCollector(simulation_duration=10.0)
        s = m.summary()
        assert s["generated"] == 0
        assert s["completed"] == 0
        assert s["dropped"] == 0
        assert s["average_latency"] == 0.0
        assert s["p95_latency"] == 0.0
        assert s["throughput"] == 0.0
        assert s["component_utilization"] == {}

    def test_with_completions(self):
        m = MetricsCollector(simulation_duration=10.0)
        for i in range(5):
            m.record_generation()
        latencies = [1.0, 2.0, 3.0, 4.0, 5.0]
        for i, lat in enumerate(latencies):
            m.record_completion(request_id=i, latency=lat)

        s = m.summary()
        assert s["generated"] == 5
        assert s["completed"] == 5
        assert s["dropped"] == 0
        assert s["average_latency"] == 3.0
        assert s["throughput"] == 0.5

    def test_dropped_count(self):
        m = MetricsCollector(simulation_duration=10.0)
        for _ in range(10):
            m.record_generation()
        for i in range(7):
            m.record_completion(request_id=i, latency=1.0)

        s = m.summary()
        assert s["dropped"] == 3

    def test_utilization(self):
        m = MetricsCollector(simulation_duration=10.0)
        m.record_busy_time("svc", 5.0)
        s = m.summary()
        assert s["component_utilization"]["svc"] == 0.5
