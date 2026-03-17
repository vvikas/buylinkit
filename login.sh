#!/bin/bash
# Run once to log in to each grocery site and set your delivery location.
# Usage:  ./login.sh              (all sites)
#         ./login.sh blinkit      (one site only)
cd "$(dirname "$0")"
source .venv/bin/activate

if [ -n "$1" ]; then
    python3 main.py --login --sites "$@"
else
    python3 main.py --login
fi
