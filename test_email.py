#!/usr/bin/env python3
"""
Test email sending functionality with mock
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_email_service_mock():
    """Test email service with mocked sending"""
    try:
        from email_service import EmailService

        service = EmailService()
        print("✅ Email service initialized")

        # Test connection (this will actually try to connect to Gmail)
        print("🔍 Testing Gmail connection...")
        connection_ok = await service.test_connection()

        if connection_ok:
            print("✅ Gmail connection successful!")
            print("📧 Ready to send emails")
            return True
        else:
            print("❌ Gmail connection failed")
            print("   Check your credentials in .env file")
            return False

    except Exception as e:
        print(f"❌ Email service test failed: {e}")
        return False

async def test_email_validation():
    """Test email validation without sending"""
    try:
        from pydantic import ValidationError
        from main import EmailRequest

        # Test valid email
        valid_request = EmailRequest(
            to_email="self@6ray.com",
            subject="Test Email",
            message="This is a test message",
            from_name="Test Sender"
        )
        print("✅ Valid email request created")
        print(f"   To: {valid_request.to_email}")
        print(f"   Subject: {valid_request.subject}")

        # Test invalid email
        try:
            invalid_request = EmailRequest(
                to_email="invalid-email",
                subject="Test",
                message="Test"
            )
            print("❌ Email validation not working")
            return False
        except ValidationError:
            print("✅ Email validation working correctly")
            return True

    except Exception as e:
        print(f"❌ Email validation test failed: {e}")
        return False

async def main():
    """Run email tests"""
    print("📧 Testing Email Functionality")
    print("=" * 40)

    tests = [
        ("Email Validation", test_email_validation),
        ("Gmail Connection", test_email_service_mock),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n🧪 Testing {test_name}...")
        try:
            result = await test_func()
            if result:
                passed += 1
            else:
                print(f"❌ {test_name} test failed")
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {e}")

    print("\n" + "=" * 40)
    print(f"📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All email tests passed!")
        print("\n🚀 Your Email API is ready!")
        print("   - Gmail credentials: ✅ Configured")
        print("   - Email validation: ✅ Working")
        print("   - Gmail connection: ✅ Successful")
        print("\n📱 Ready for iOS app integration!")
        return True
    else:
        print("❌ Some tests failed. Please check your Gmail credentials.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)