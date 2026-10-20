#!/usr/bin/env python3
"""token-pet entry point: pet"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from petlib import cli  # noqa: E402

sys.exit(cli.run(sys.argv[1:] or ["status"]))
