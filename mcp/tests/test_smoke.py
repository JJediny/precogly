"""Smoke tests for precogly_mcp."""

from __future__ import annotations

import precogly_mcp


def test_version_is_set() -> None:
    assert precogly_mcp.__version__


def test_console_script_entry_point_is_importable() -> None:
    """`precogly-mcp` resolves here, so a rename fails a test rather than a shell."""
    from precogly_mcp.server import main

    assert callable(main)
