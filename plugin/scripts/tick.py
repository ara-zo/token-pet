#!/usr/bin/env python3
"""token-pet entry point: tick"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from petlib import cli  # noqa: E402

sys.exit(cli.run(["session-start"]))
