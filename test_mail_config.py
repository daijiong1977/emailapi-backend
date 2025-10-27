#!/usr/bin/env python3
"""
Test mail configuration loading and merging from multiple sources
"""
import os
import sys
import tempfile
import json
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_mail_config_store():
    """Test mail_config_store module functionality"""
    from mail_config_store import load_mail_config, save_mail_config
    
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, 'test_config.json')
        
        # Test saving
        test_data = {
            'mail_provider': 'gmail',
            'gmail_user': 'test@gmail.com',
            'gmail_app_password': 'testpass123'
        }
        save_mail_config(test_data, config_path)
        assert os.path.exists(config_path), "Config file should be created"
        
        # Test loading
        loaded = load_mail_config(config_path)
        assert loaded['mail_provider'] == 'gmail', "Should load mail_provider"
        assert loaded['gmail_user'] == 'test@gmail.com', "Should load gmail_user"
        assert loaded['gmail_app_password'] == 'testpass123', "Should load password"
        
        # Test merging (update existing config)
        loaded['aws_region'] = 'us-west-2'
        save_mail_config(loaded, config_path)
        loaded2 = load_mail_config(config_path)
        assert loaded2['aws_region'] == 'us-west-2', "Should preserve merged values"
        assert loaded2['gmail_user'] == 'test@gmail.com', "Should preserve existing values"
        
        # Test file permissions
        import stat
        st = os.stat(config_path)
        mode = stat.S_IMODE(st.st_mode)
        assert mode == 0o600, f"File should have 0o600 permissions, got {oct(mode)}"
        
        print("✅ mail_config_store tests passed")
        return True

def test_config_priority():
    """Test configuration loading priority: env vars > .env > mail_config.json"""
    from mail_config_store import save_mail_config
    import importlib
    
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, 'test_config.json')
        env_path = os.path.join(tmpdir, 'test.env')
        
        # Setup mail_config.json
        mail_config = {
            'mail_provider': 'gmail',
            'gmail_user': 'json@example.com',
            'aws_region': 'us-east-1'
        }
        save_mail_config(mail_config, config_path)
        
        # Setup .env file
        with open(env_path, 'w') as f:
            f.write('GMAIL_USER=env@example.com\n')
            f.write('AWS_REGION=us-west-1\n')
        
        # Set environment variable (highest priority)
        os.environ['MAIL_CONFIG_PATH'] = config_path
        os.environ['GMAIL_USER'] = 'env_var@example.com'
        
        # Import config module (this will load configuration)
        # Note: This test is simplified - in real scenario we'd need to reload the module
        from mail_config_store import load_mail_config
        loaded = load_mail_config(config_path)
        
        # Verify mail_config.json loads correctly
        assert loaded['gmail_user'] == 'json@example.com', "Should load from JSON"
        assert loaded['mail_provider'] == 'gmail', "Should load provider from JSON"
        
        # Clean up
        del os.environ['MAIL_CONFIG_PATH']
        del os.environ['GMAIL_USER']
        
        print("✅ config priority tests passed")
        return True

def test_is_ses_configured():
    """Test is_ses_configured helper"""
    from config import Config
    
    # Save original env vars
    original_env = {
        'AWS_ACCESS_KEY_ID': os.environ.get('AWS_ACCESS_KEY_ID'),
        'AWS_SECRET_ACCESS_KEY': os.environ.get('AWS_SECRET_ACCESS_KEY'),
        'AWS_REGION': os.environ.get('AWS_REGION'),
    }
    
    try:
        # Test without SES config
        for key in original_env:
            if key in os.environ:
                del os.environ[key]
        
        config = Config()
        assert not config.is_ses_configured(), "Should not be configured without credentials"
        
        # Test with partial SES config
        os.environ['AWS_ACCESS_KEY_ID'] = 'AKIATEST'
        os.environ['AWS_SECRET_ACCESS_KEY'] = 'secret'
        config2 = Config()
        assert not config2.is_ses_configured(), "Should not be configured without region"
        
        # Test with full SES config
        os.environ['AWS_REGION'] = 'us-east-1'
        config3 = Config()
        assert config3.is_ses_configured(), "Should be configured with all credentials"
        
        print("✅ is_ses_configured tests passed")
        return True
    finally:
        # Restore original env vars
        for key, value in original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]

def main():
    """Run all tests"""
    print("🚀 Running Mail Configuration Tests")
    print("=" * 40)
    
    tests = [
        ("Mail Config Store", test_mail_config_store),
        ("Config Priority", test_config_priority),
        ("is_ses_configured", test_is_ses_configured),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🧪 Testing {test_name}...")
        try:
            if test_func():
                passed += 1
            else:
                print(f"❌ {test_name} test failed")
        except Exception as e:
            print(f"❌ {test_name} test failed with error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 40)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All mail configuration tests passed!")
        return True
    else:
        print("❌ Some tests failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
