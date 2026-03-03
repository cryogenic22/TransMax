import pytest
import requests
import time
import uuid

API_URL = "http://localhost:8001/api/v1/translations"
TIMEOUT = 60

@pytest.mark.e2e
def test_golden_path_lifecycle():
    """
    TMX-E2E-001: Golden Path Integration Test.
    Requires a running server on localhost:8001.
    """
    request_id = str(uuid.uuid4())
    payload = {
        "source_language": "en",
        "target_language": "ja",
        "request_id": request_id,
        "document_name": "golden_path_test.txt",
        "text_content": "The patient must take 10mg of Aspirin daily. Severe allergic reaction possible.",
        "profile": {
            "archetype": "SAFETY_CRITICAL",
            "tier": "TIER_A",
            "modality": "NARRATIVE"
        },
        "domain": "pharma"
    }

    try:
        resp = requests.post(API_URL + "/", json=payload, timeout=5)
    except requests.exceptions.ConnectionError:
        pytest.skip("API is not reachable. Ensure the server is running on localhost:8001")

    resp.raise_for_status()
    data = resp.json()
    job_id = data["job_id"]

    # Poll for completion
    start_time = time.time()
    final_status = None
    while time.time() - start_time < TIMEOUT:
        r = requests.get(f"{API_URL}/{job_id}")
        r.raise_for_status()
        status = r.json()["status"]
        if status in ["translated", "approved", "review_required"]:
            final_status = status
            break
        if status == "failed":
            pytest.fail("Job failed processing")
        time.sleep(2)

    if not final_status:
        pytest.fail(f"Job timed out after {TIMEOUT}s")

    # Verify Audit Bundle
    r_audit = requests.get(f"{API_URL}/{job_id}/audit_bundle")
    assert r_audit.status_code == 200
    audit_data = r_audit.json()
    assert audit_data["chain_head_hash"] != "N/A"
    assert len(audit_data["entries"]) > 0

if __name__ == "__main__":
    test_golden_path_lifecycle()
