"""Compatibility entrypoint for the modular Nested Desktop bridge."""

from fourdeus_backend.nested_desktop import *  # noqa: F403
from fourdeus_backend.nested_desktop.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
