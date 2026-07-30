"""Decky Loader entrypoint for 4deus Mod."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fourdeus_backend.plugin import Plugin

__all__ = ["Plugin"]
