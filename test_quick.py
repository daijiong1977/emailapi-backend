#!/usr/bin/env python3
"""
Quick test script for Email API
Tests basic functionality without requiring Gmail credentials
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all required modules can be imported"""
    try:
        from fastapi import FastAPI
        from pydantic import BaseModel, EmailStr
        from config import Config
        from email_service import EmailService
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_config():
    """Test configuration class"""
    try:
        from config import Config
        config = Config()
        print("✅ Config class initialized")
        print(f"   Gmail configured: {config.is_gmail_configured()}")
        return True
    except Exception as e:
        print(f"❌ Config test failed: {e}")
        return False

def test_email_service():
    """Test email service initialization"""
    try:
        from email_service import EmailService
        service = EmailService()
        print("✅ Email service initialized")
        return True
    except Exception as e:
        print(f"❌ Email service test failed: {e}")
        return False

def test_models():
    """Test Pydantic models"""
    try:
        from pydantic import BaseModel, EmailStr

        class TestEmailRequest(BaseModel):
            to_email: EmailStr
            subject: str
            message: str
            from_name: str = None

        # Test valid email
        request = TestEmailRequest(
            to_email="self@6ray.com",
            subject="Test Subject",
            message="Test message"
        )
        print("✅ Pydantic models working")
        print(f"   Valid email: {request.to_email}")

        # Test invalid email (should raise validation error)
        try:
            invalid_request = TestEmailRequest(
                to_email="invalid-email",
                subject="Test",
                message="Test"
            )
            print("❌ Email validation not working")
            return False
        except Exception:
            print("✅ Email validation working correctly")
            return True

    except Exception as e:
        print(f"❌ Model test failed: {e}")
        return False

def test_fastapi_app():
    """Test FastAPI app creation"""
    try:
        from fastapi import FastAPI
        from main import app

        # Check if app is FastAPI instance
        assert isinstance(app, FastAPI)
        print("✅ FastAPI app created successfully")
        print(f"   Title: {app.title}")
        print(f"   Version: {app.version}")
        return True
    except Exception as e:
        print(f"❌ FastAPI app test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Running Email API Tests")
    print("=" * 40)

    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Email Service", test_email_service),
        ("Pydantic Models", test_models),
        ("FastAPI App", test_fastapi_app),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n🧪 Testing {test_name}...")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} test failed")

    print("\n" + "=" * 40)
    print(f"📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! The API is ready for deployment.")
        print("\n📋 Next steps:")
        print("1. Set up Gmail credentials (will prompt on first run)")
        print("2. Run: python main.py")
        print("3. Test API at: http://localhost:8002/docs")
        return True
    else:
        print("❌ Some tests failed. Please fix the issues before deploying.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)