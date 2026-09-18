"""Resolve platform source sets without duplicating shared release locks."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_sources(platform='linux'):
    shared = json.loads((ROOT / 'sources.json').read_text())
    if platform == 'linux':
        return shared
    if platform != 'macos':
        raise ValueError('Unknown platform: ' + platform)
    macos = json.loads((ROOT / 'sources-macos.json').read_text())
    return {**{name: shared[name] for name in macos['shared']}, **macos['extra']}
