"""Ollama readiness check for the configured Qwen model (answering lives in Lab 8B's ask())."""

from types import ModuleType

import requests

from .config import Settings


def _canonical_model_name(name: str) -> str:
    name = name.strip()
    if name and ':' not in name.rsplit('/', 1)[-1]:
        name += ':latest'
    return name


class QwenTextToSQL:
    def __init__(self, config: Settings, lab8b: ModuleType):
        self.config = config
        self.lab8b = lab8b

    def available(self) -> bool:
        """Daemon reachable and the configured model listed as installed."""
        try:
            response = requests.get(f'{self.config.ollama_url}/api/tags', timeout=3)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            return False
        if not isinstance(payload, dict) or not isinstance(payload.get('models'), list):
            return False
        wanted = _canonical_model_name(self.config.ollama_model)
        if not wanted:
            return False
        return any(
            isinstance(item, dict) and any(
                isinstance(item.get(key), str)
                and _canonical_model_name(item[key]) == wanted
                for key in ('name', 'model'))
            for item in payload['models'])
