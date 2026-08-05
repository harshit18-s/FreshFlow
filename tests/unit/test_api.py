"""
Unit tests for FastAPI Service in FreshFlow AI.
"""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"
    assert "model_loaded" in data


def test_predict_endpoint_model_not_loaded():
    # Model is None in test environment unless loaded
    payload = {
        "store_id": 1001,
        "product_id": 5001,
        "store_cluster": "Cluster A",
        "volume_band": "High",
        "discount_factor": 1.0,
        "year": 2026,
        "month": 8,
        "day": 5,
        "hour": 12
    }
    response = client.post("/predict", json=payload)
    # Returns 503 if model is not loaded in memory
    assert response.status_code in [200, 503]
