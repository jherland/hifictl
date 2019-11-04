#!/bin/sh

if python3 -c 'import flake8' 2>/dev/null; then
    HAS_FLAKE8=1
fi

set -e

python3 -m pytest "$@"
if test -n "$HAS_FLAKE8"; then
    python3 -m flake8 *.py
fi
