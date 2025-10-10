import os
import uuid
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

TEST_DB_PATH = "./test_api_keys.db"
os.environ["API_KEYS_DB"] = TEST_DB_PATH

from main import app, DB_PATH  # noqa: E402
from api_keys import init_db, disable_device

if os.path.exists(TEST_DB_PATH):
    os.remove(TEST_DB_PATH)

init_db(DB_PATH)

client = TestClient(app)


def _mint_api_key() -> str:
    response = client.post("/client/bootstrap", json={"device_id": uuid.uuid4().hex})
    assert response.status_code == 200, response.text
    return response.json()["api_key"]


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "email-api"}

def test_config_status():
    """Test configuration status endpoint"""
    response = client.get("/config/status")
    assert response.status_code == 200
    data = response.json()
    assert "gmail_configured" in data
    assert "message" in data

@patch('email_service.EmailService.send_email')
def test_send_email_success(mock_send):
    """Test successful email sending"""
    mock_send.return_value = True
    api_key = _mint_api_key()

    email_data = {
        "to_email": "self@6ray.com",
        "subject": "Test Subject",
        "message": "Test message",
        "from_name": "Test Sender"
    }

    response = client.post("/send-email", json=email_data, headers={"x-api-key": api_key})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert "queued for sending" in data["message"]
    assert "email_id" in data

def test_send_email_invalid_email():
    """Test email sending with invalid email"""
    email_data = {
        "to_email": "invalid-email",
        "subject": "Test Subject",
        "message": "Test message"
    }

    api_key = _mint_api_key()
    response = client.post("/send-email", json=email_data, headers={"x-api-key": api_key})
    # Pydantic should validate the email format
    assert response.status_code == 422  # Validation error

def test_send_email_missing_fields():
    """Test email sending with missing required fields"""
    email_data = {
        "to_email": "self@6ray.com"
        # Missing subject and message
    }

    api_key = _mint_api_key()
    response = client.post("/send-email", json=email_data, headers={"x-api-key": api_key})
    assert response.status_code == 422  # Validation error


def test_client_bootstrap_idempotent():
    device_id = uuid.uuid4().hex

    response1 = client.post(
        "/client/bootstrap",
        json={"device_id": device_id, "display_name": "QA iPhone"},
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["device_id"] == device_id
    assert data1["api_key"].count(".") == 1

    response2 = client.post(
        "/client/bootstrap",
        json={"device_id": device_id, "display_name": "QA iPhone"},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["api_key"] == data1["api_key"]
    assert data2["username"] == data1["username"]


def test_client_bootstrap_disabled_device():
    device_id = uuid.uuid4().hex

    response = client.post(
        "/client/bootstrap",
        json={"device_id": device_id},
    )
    assert response.status_code == 200
    disable_device(DB_PATH, device_id)

    blocked = client.post(
        "/client/bootstrap",
        json={"device_id": device_id},
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"].lower().startswith("device is disabled")

if __name__ == "__main__":
    pytest.main([__file__])