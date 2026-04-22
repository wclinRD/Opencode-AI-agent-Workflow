#!/usr/bin/env python3
"""Test script for SecureConfig functionality."""

import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, "src")

from leeway_integration.daemon.core import SecureConfig

def test_secure_config():
    print("Testing SecureConfig functionality...\n")
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = Path(temp_dir) / ".leeway"
        config_dir.mkdir()
        
        # Test 1: Default settings with empty values
        print("1. Testing default settings...")
        settings = {
            "api_key": "",
            "anthropic_api_key": "",
            "github_token": "",
            "brave_api_key": "",
            "audit_encryption_key": ""
        }
        secure_config = SecureConfig(settings, config_dir)
         
        # Debug what we're actually getting
        print("   DEBUG: Settings in SecureConfig:", secure_config._settings)
        api_key = secure_config.get_api_key()
        github_token = secure_config.get_github_token()
        brave_api_key = secure_config.get_brave_api_key()
        print(f"   DEBUG: api_key='{api_key}', github_token='{github_token}', brave_api_key='{brave_api_key}'")
        # Should return empty string for all sensitive keys when not set but present in settings
        assert secure_config.get_api_key() == ""
        assert secure_config.get_github_token() == ""
        assert secure_config.get_brave_api_key() == ""
        print("   ✅ Returns empty string for unset but present sensitive keys")
        
        # Test 2: Settings.json values
        print("\n2. Testing settings.json values...")
        settings_with_values = {
            "api_key": "sk-test-123",
            "anthropic_api_key": "sk-ant-test-456",
            "github_token": "ghp_testtoken",
            "brave_api_key": "brave-test-key",
            "audit_encryption_key": "audit-test-key-789"
        }
        secure_config = SecureConfig(settings_with_values, config_dir)
        
        # Should return values from settings.json (with warning)
        assert secure_config.get_api_key() == "sk-test-123"
        assert secure_config.get_github_token() == "ghp_testtoken"
        assert secure_config.get_brave_api_key() == "brave-test-key"
        print("   ✅ Returns values from settings.json")
        
        # Test 3: Environment variable override
        print("\n3. Testing environment variable override...")
        os.environ["LEEWAY_API_KEY"] = "sk-env-override"
        os.environ["LEEWAY_GITHUB_TOKEN"] = "ghp-env-token"
        
        secure_config = SecureConfig(settings_with_values, config_dir)
        
        # Environment variables should take precedence
        assert secure_config.get_api_key() == "sk-env-override"
        assert secure_config.get_github_token() == "ghp-env-token"
        # Brave API key should still come from settings since no env var set
        assert secure_config.get_brave_api_key() == "brave-test-key"
        print("   ✅ Environment variables take precedence")
        
        # Clean up environment variables
        del os.environ["LEEWAY_API_KEY"]
        del os.environ["LEEWAY_GITHUB_TOKEN"]
        
        # Test 4: .env file
        print("\n4. Testing .env file...")
        env_file = config_dir / ".env"
        with open(env_file, "w") as f:
            f.write("API_KEY=sk-dotenv-key\n")
            f.write("GITHUB_TOKEN=ghp-dotenv-token\n")
            f.write("BRAVE_API_KEY=brave-dotenv-key\n")
        
        # Debug: Check if file exists and contents
        print(f"   DEBUG: .env file exists: {env_file.exists()}")
        if env_file.exists():
            with open(env_file, "r") as f:
                contents = f.read()
                print(f"   DEBUG: .env file contents: {repr(contents)}")
        
        secure_config = SecureConfig(settings, config_dir)  # settings with empty values
        
        # Debug: Check what _load_env_file returns
        env_vars = secure_config._load_env_file()
        print(f"   DEBUG: _load_env_file returned: {env_vars}")
        print(f"   DEBUG: _env_cache after loading: {secure_config._env_cache}")
        
        # Should get values from .env file
        api_key = secure_config.get_api_key()
        github_token = secure_config.get_github_token()
        brave_api_key = secure_config.get_brave_api_key()
        print(f"   DEBUG: get_api_key()='{api_key}', get_github_token()='{github_token}', get_brave_api_key()='{brave_api_key}'")
        
        assert api_key == "sk-dotenv-key"
        assert github_token == "ghp-dotenv-token"
        assert brave_api_key == "brave-dotenv-key"
        print("   ✅ Returns values from .env file")
        
        # Test 5: Keychain simulation (we'll skip actual keychain testing as it requires user interaction)
        print("\n5. Testing keychain simulation (skipped - requires user interaction)...")
        print("   ⚠️  Keychain testing skipped in automated test")
        
        # Test 6: Priority order verification
        print("\n6. Testing priority order...")
        # Set up all sources
        settings_priority = {
            "api_key": "sk-settings",
            "anthropic_api_key": "sk-ant-settings",
            "github_token": "ghp-settings",
            "brave_api_key": "brave-settings",
            "audit_encryption_key": "audit-settings"
        }
        
        env_file_priority = config_dir / ".env"
        with open(env_file_priority, "w") as f:
            f.write("API_KEY=sk-dotenv\n")
            f.write("GITHUB_TOKEN=ghp-dotenv\n")
        
        os.environ["LEEWAY_API_KEY"] = "sk-env"
        os.environ["LEEWAY_GITHUB_TOKEN"] = "ghp-env"
        
        secure_config = SecureConfig(settings_priority, config_dir)
        
        # Environment should win
        assert secure_config.get_api_key() == "sk-env"
        assert secure_config.get_github_token() == "ghp-env"
        # Dotenv should win over settings for BRAVE_API_KEY (no env var set)
        assert secure_config.get_brave_api_key() == "brave-dotenv"
        # Settings should win for audit_encryption_key (no env or dotenv)
        assert secure_config.get("audit_encryption_key") == "audit-settings"
        print("   ✅ Priority order: Environment > .env > Settings.json")
        
        # Clean up
        del os.environ["LEEWAY_API_KEY"]
        del os.environ["LEEWAY_GITHUB_TOKEN"]
    
    print("\n✅ All SecureConfig tests passed!")

if __name__ == "__main__":
    test_secure_config()