#!/usr/bin/env python3
"""Process data script."""
import sys

print(f"Processing: {sys.argv[1] if len(sys.argv) > 1 else 'stdin'}")
