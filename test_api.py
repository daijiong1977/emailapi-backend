import pytest
from fastapi.testclient import TestClient
from main import app
import os
from unittest.mock import patch, MagicMock

client = TestClient(app)

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

    email_data = {
        "to_email": "self@6ray.com",
        "subject": "Test Subject",
        "message": "Test message",
        "from_name": "Test Sender"
    }

    response = client.post("/send-email", json=email_data)
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

    response = client.post("/send-email", json=email_data)
    # Pydantic should validate the email format
    assert response.status_code == 422  # Validation error

def test_send_email_missing_fields():
    """Test email sending with missing required fields"""
    email_data = {
        "to_email": "self@6ray.com"
        # Missing subject and message
    }

    response = client.post("/send-email", json=email_data)
    assert response.status_code == 422  # Validation error

if __name__ == "__main__":
    pytest.main([__file__])