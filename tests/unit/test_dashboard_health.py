"""
Unit tests for Dashboard API Health & Simulation detection logic.
"""

from unittest.mock import Mock, patch

import requests


def check_api_status():
    """Helper function logic extracted from dashboard app.py."""
    try:
        r = requests.get("http://localhost:8000/health", timeout=1.5)
        return (r.status_code == 200 and r.json().get("model_loaded", False))
    except Exception:
        return False

def test_api_status_online():
    mock_resp = Mock(status_code=200)
    mock_resp.json.return_value = {"status": "healthy", "model_loaded": True}
    with patch("requests.get", return_value=mock_resp):
        assert check_api_status() is True

def test_api_status_offline_connection_error():
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Connection refused")):
        assert check_api_status() is False

def test_api_status_model_not_loaded():
    mock_resp = Mock(status_code=200)
    mock_resp.json.return_value = {"status": "healthy", "model_loaded": False}
    with patch("requests.get", return_value=mock_resp):
        assert check_api_status() is False
