"""Compatibility wrapper for the versioned xFG v3 training workflow."""

from __future__ import annotations

import sys

from app.pipeline.cli import main

if __name__ == "__main__":
    main(["train", *sys.argv[1:]])
