# tests/test_config_manager.py
import os
import json
import pytest
import tempfile
from unittest.mock import patch, mock_open
from src.config_manager import ConfigManager, ConfigurationError

class TestConfigManager:
    
    def test_get_region_default(self):
        """Test getting default region."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.ini")
            accounts_file = os.path.join(tmpdir, "accounts.json")
            
            with patch("os.environ.get", return_value=None):
                config_manager = ConfigManager(config_file, accounts_file)
                region = config_manager.get_region()
                assert region == "ap-southeast-2"
                
    def test_get_region_env_override(self):
        """Test region from environment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.ini")
            accounts_file = os.path.join(tmpdir, "accounts.json")
            
            with patch("os.environ.get", return_value="us-west-2"):
                config_manager = ConfigManager(config_file, accounts_file)
                region = config_manager.get_region()
                assert region == "us-west-2"
                
    def test_get_region_param_override(self):
        """Test region from parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.ini")
            accounts_file = os.path.join(tmpdir, "accounts.json")
            
            with patch("os.environ.get", return_value="us-west-2"):
                config_manager = ConfigManager(config_file, accounts_file)
                region = config_manager.get_region("eu-central-1")
                assert region == "eu-central-1"
                
    def test_get_accounts(self):
        """Test getting accounts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.ini")
            accounts_file = os.path.join(tmpdir, "accounts.json")
            
            accounts_data = {
                "accounts": [
                    {"name": "prod", "account_id": "123456789012"},
                    {"name": "dev", "account_id": "210987654321"}
                ]
            }
            
            with open(accounts_file, 'w') as f:
                json.dump(accounts_data, f)
                
            config_manager = ConfigManager(config_file, accounts_file)
            accounts = config_manager.get_accounts()
            
            assert len(accounts) == 2
            assert accounts[0]["name"] == "prod"
            assert accounts[1]["account_id"] == "210987654321"
            
    def test_get_filtered_accounts(self):
        """Test filtering accounts by name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.ini")
            accounts_file = os.path.join(tmpdir, "accounts.json")
            
            accounts_data = {
                "accounts": [
                    {"name": "prod", "account_id": "123456789012"},
                    {"name": "dev", "account_id": "210987654321"},
                    {"name": "test", "account_id": "123123123123"}
                ]
            }
            
            with open(accounts_file, 'w') as f:
                json.dump(accounts_data, f)
                
            config_manager = ConfigManager(config_file, accounts_file)
            accounts = config_manager.get_accounts(["prod", "test"])
            
            assert len(accounts) == 2
            assert accounts[0]["name"] == "prod"
            assert accounts[1]["name"] == "test"
            
    def test_get_tag_config(self):
        """Test getting tag configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.ini")
            accounts_file = os.path.join(tmpdir, "accounts.json")
            
            config_manager = ConfigManager(config_file, accounts_file)
            tag_key, tag_value = config_manager.get_tag_config()
            
            assert tag_key == "scheduled"
            assert tag_value == "enabled"
