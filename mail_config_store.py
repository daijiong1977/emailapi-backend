"""
Mail configuration storage module.
Handles loading and saving mail provider configuration to/from JSON file.
"""
import json
import os
from typing import Dict, Any, Optional
import tempfile


def load_mail_config(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load mail configuration from JSON file.
    
    Args:
        path: Optional path to config file. If not provided, uses MAIL_CONFIG_PATH env var
              or defaults to ./mail_config.json
    
    Returns:
        Dictionary containing mail configuration. Returns empty dict if file doesn't exist.
    """
    if path is None:
        path = os.getenv('MAIL_CONFIG_PATH', './mail_config.json')
    
    if not os.path.exists(path):
        return {}
    
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Failed to load mail config from {path}: {e}")
        return {}


def save_mail_config(data: Dict[str, Any], path: Optional[str] = None) -> None:
    """
    Save mail configuration to JSON file with atomic write and restrictive permissions.
    
    Args:
        data: Dictionary containing mail configuration
        path: Optional path to config file. If not provided, uses MAIL_CONFIG_PATH env var
              or defaults to ./mail_config.json
    """
    if path is None:
        path = os.getenv('MAIL_CONFIG_PATH', './mail_config.json')
    
    # Create directory if it doesn't exist
    dir_path = os.path.dirname(path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, mode=0o700, exist_ok=True)
    
    # Atomic write: write to temp file then replace
    dir_name = os.path.dirname(path) or '.'
    with tempfile.NamedTemporaryFile(
        mode='w',
        dir=dir_name,
        delete=False,
        prefix='.mail_config_',
        suffix='.tmp'
    ) as tmp_file:
        tmp_path = tmp_file.name
        json.dump(data, tmp_file, indent=2)
    
    # Set restrictive permissions (best effort)
    try:
        os.chmod(tmp_path, 0o600)
    except Exception as e:
        print(f"Warning: Could not set restrictive permissions on {tmp_path}: {e}")
    
    # Replace old file with new one
    os.replace(tmp_path, path)
