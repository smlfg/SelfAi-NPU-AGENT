"""
Shared configuration loader for all agents.
"""

import yaml
from pathlib import Path
from typing import Dict, Any


def load_playbook_config(config_path: str) -> Dict[str, Any]:
    """
    Load and parse playbook configuration.

    Args:
        config_path: Path to playbook.yaml

    Returns:
        Parsed configuration dictionary
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    return config


def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate configuration against schema.

    Args:
        config: Configuration dictionary

    Returns:
        True if valid, raises ValueError otherwise
    """
    required_fields = ['name', 'agent_id', 'version', 'ports']

    playbook = config.get('playbook', {})

    for field in required_fields:
        if field not in playbook:
            raise ValueError(f"Missing required field: playbook.{field}")

    # Validate agent_id format
    agent_id = playbook.get('agent_id', '')
    if not agent_id.startswith('agent') or '_' not in agent_id:
        raise ValueError(f"Invalid agent_id format: {agent_id}")

    # Validate version format
    version = playbook.get('version', '')
    parts = version.split('.')
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Invalid version format: {version}")

    # Validate ports
    ports = playbook.get('ports', [])
    if not isinstance(ports, list) or not ports:
        raise ValueError("Ports must be a non-empty list")

    for port in ports:
        if not isinstance(port, int) or port < 1024 or port > 65535:
            raise ValueError(f"Invalid port: {port}")

    return True
