"""Utility helpers for DEVO."""

from typing import Dict, Any, Optional
import yaml
import json
from pathlib import Path


def load_config(path: Optional[str]) -> Dict[str, Any]:
    """
    Load YAML or JSON configuration. If path is None or file missing, returns {}.
    """
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        if p.suffix.lower() in (".yml", ".yaml"):
            with p.open("r", encoding="utf-8") as fh:
                return yaml.safe_load(fh) or {}
        elif p.suffix.lower() == ".json":
            with p.open("r", encoding="utf-8") as fh:
                return json.load(fh)
    except Exception:
        return {}
    return {}
