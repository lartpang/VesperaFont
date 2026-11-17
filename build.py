#!/usr/bin/env python3
"""One configuration-driven entry point for both Vespera families."""
import sys

# This entry point keeps Python bytecode caches out of the source checkout.
sys.dont_write_bytecode = True

from fontviber.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
