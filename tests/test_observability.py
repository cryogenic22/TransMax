from fastapi.testclient import TestClient
from app.main import app
from app.services.observability import ObservabilityService

client = TestClient(app)

def test_middleware_latency_header():
    # Call health check
    response = client.get("/health")
    assert response.status_code == 200
    
    # Check header
    assert "X-Processing-Time-Ms" in response.headers
    latency = float(response.headers["X-Processing-Time-Ms"])
    assert latency >= 0

def test_metrics_tracking():
    # Make a few requests
    initial_count = ObservabilityService.get_metrics()["total_requests"]
    client.get("/health")
    client.get("/health")
    
    metrics = ObservabilityService.get_metrics()
    assert metrics["total_requests"] == initial_count + 2
    assert metrics["total_latency_ms"] > 0
