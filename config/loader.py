from typing import Dict, Any

def load() -> Dict[str, Any]:
    """
    Standard implementation.
    As needed, return a small config dict (data/engine/report); read defaults.yaml if present; allow env overrides.
    """
    pass

# Suggested helpers:
# - _load_yaml(path) -> dict
# - _merge_env(cfg) -> dict