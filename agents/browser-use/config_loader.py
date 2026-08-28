import json
import os
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "config.json"


@lru_cache(maxsize=1)
def load_app_config():
    """Load project settings from the root config.json file."""
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
            config = json.load(config_file)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required configuration file not found: {CONFIG_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in configuration file: {CONFIG_PATH}") from exc

    for section in ("llm", "database", "seaweedfs", "runtime", "environment"):
        if section not in config:
            raise RuntimeError(f"Missing '{section}' section in {CONFIG_PATH}")
    return config


def apply_environment_config():
    """Make config.json environment settings authoritative for legacy providers."""
    environment = load_app_config()["environment"]
    for key, value in environment.items():
        os.environ[str(key)] = str(value)


def get_llm_profile(profile_name=None, profile_selector="default_profile"):
    """Return a validated LLM profile from config.json."""
    llm_config = load_app_config()["llm"]
    selected_name = profile_name or llm_config.get(profile_selector)
    profiles = llm_config.get("profiles", {})
    if selected_name not in profiles:
        available = ", ".join(sorted(profiles))
        raise RuntimeError(
            f"Unknown LLM profile '{selected_name}'. Available profiles: {available}"
        )

    profile = profiles[selected_name]
    required_fields = ("api_key", "base_url", "model", "model_name")
    missing = [field for field in required_fields if not profile.get(field)]
    if missing:
        raise RuntimeError(
            f"LLM profile '{selected_name}' is missing: {', '.join(missing)}"
        )
    return selected_name, profile.copy()


apply_environment_config()
