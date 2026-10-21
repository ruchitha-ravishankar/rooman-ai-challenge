"""API endpoint and validation tests using FastAPI TestClient."""

import pytest
from fastapi.testclient import TestClient
from mcp_defense_lab.api.app import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "available_defenses" in data
    assert len(data["available_defenses"]) >= 5


def test_list_defenses_endpoint():
    resp = client.get("/api/defenses")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 5
    ids = [d["id"] for d in data]
    assert "intent_alignment_defense" in ids
    assert "no_defense_baseline" in ids
    assert "keyword_rule_scanner" in ids


def test_list_cases_endpoint():
    resp = client.get("/api/cases?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 10
    assert "case_id" in data[0]


def test_create_and_fetch_experiment():
    payload = {
        "title": "API Automated Test",
        "defense_name": "keyword_rule_scanner",
        "provider": "scripted",
        "scripted_mode": "naive_compliant",
        "sample_count": 10,
        "seed": 42,
    }
    create_resp = client.post("/api/experiments", json=payload)
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert "experiment_id" in created
    exp_id = created["experiment_id"]

    # Fetch experiment list
    list_resp = client.get("/api/experiments")
    assert list_resp.status_code == 200
    exp_list = list_resp.json()
    assert any(e["id"] == exp_id for e in exp_list)

    # Fetch details
    detail_resp = client.get(f"/api/experiments/{exp_id}")
    assert detail_resp.status_code == 200
    details = detail_resp.json()
    assert details["title"] == "API Automated Test"
    assert len(details["cases"]) == 10

    # Fetch results
    results_resp = client.get(f"/api/experiments/{exp_id}/results")
    assert results_resp.status_code == 200
    assert "report" in results_resp.json()


def test_invalid_experiment_payload_rejection():
    # Unknown defense
    resp = client.post("/api/experiments", json={"defense_name": "nonexistent_defense"})
    assert resp.status_code == 400

    # Sample size out of bounds (< 2)
    resp2 = client.post("/api/experiments", json={"defense_name": "no_defense_baseline", "sample_count": 0})
    assert resp2.status_code == 422


def test_fuzz_run_endpoint():
    payload = {
        "defense_name": "keyword_rule_scanner",
        "max_mutations_per_case": 1,
        "sample_count": 6,
        "seed": 42,
    }
    resp = client.post("/api/fuzz-runs", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "fuzz_run_id" in data
    assert "delta_asr" in data
