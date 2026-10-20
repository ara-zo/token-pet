#!/bin/sh
# Direct status line entry (for local development). `/pet setup` installs a
# self-locating bootstrap in ~/.claude/pet/ instead, which survives plugin updates.
exec python3 "$(dirname "$0")/scripts/pet.py" statusline
