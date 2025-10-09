#!/usr/bin/env python3
"""
Full API workflow test
"""

import asyncio
import sys
import os
import subprocess
import time
import requests
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_full_api_workflow():
    """Test the complete API workflow"""
    print("🔄 Testing Full API Workflow")
    print("=" * 40)

    # Start the server in background
    print("🚀 Starting API server...")
    server = subprocess.Popen(
        ['python3', 'main.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for server to start
    await asyncio.sleep(3)

    try:
        base_url = "http://localhost:8002"

        # Test 1: Health check
        print("🏥 Testing health endpoint...")
        response = requests.get(f"{base_url}/health", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "email-api"
        print("✅ Health check passed")

        # Test 2: Config status
        print("⚙️ Testing config status...")
        response = requests.get(f"{base_url}/config/status", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert "gmail_configured" in data
        assert data["gmail_configured"] == True
        print("✅ Config status passed")

        # Test 3: Send email (this will actually try to send)
        print("📧 Testing email sending...")
        email_data = {
            "to_email": "self@6ray.com",  # Test recipient
            "subject": "API Test Email",
            "message": "This is a test email from the Email API service.",
            "from_name": "Email API Test"
        }

        response = requests.post(
            f"{base_url}/send-email",
            json=email_data,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            assert data["success"] == True
            assert "message" in data
            assert "email_id" in data
            print("✅ Email sending queued successfully")
            print(f"   Email ID: {data['email_id']}")
        else:
            print(f"❌ Email sending failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

        # Test 4: Invalid email validation
        print("🔍 Testing email validation...")
        invalid_email_data = {
            "to_email": "invalid-email",
            "subject": "Test",
            "message": "Test"
        }

        response = requests.post(
            f"{base_url}/send-email",
            json=invalid_email_data,
            timeout=5
        )

        if response.status_code == 422:  # Validation error
            print("✅ Email validation working correctly")
        else:
            print(f"❌ Email validation not working: {response.status_code}")
            return False

        print("\n🎉 Full API workflow test completed successfully!")
        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False
    except AssertionError as e:
        print(f"❌ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    finally:
        # Stop server
        server.terminate()
        server.wait()
        print("🛑 Server stopped")

async def main():
    """Main test function"""
    print("🚀 Email API Full System Test")
    print("=" * 50)

    success = await test_full_api_workflow()

    print("\n" + "=" * 50)
    if success:
        print("🎉 ALL TESTS PASSED!")
        print("\n✅ Your Email API is fully functional and ready for:")
        print("   • iOS app integration")
        print("   • EC2 deployment")
        print("   • Production use")
        print("\n📋 Deployment ready:")
        print("   1. Copy files to EC2 instance")
        print("   2. Run: ./setup.sh")
        print("   3. Start service with systemd")
        print("   4. Configure iOS app to use your EC2 IP:8002")
    else:
        print("❌ Some tests failed. Please check the errors above.")

    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)