"""Equivalent module entry point for the bounds command group."""

import sys

from ..cli import main

raise SystemExit(main(["bound", *sys.argv[1:]]))
