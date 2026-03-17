#!/bin/bash
# Run once to log in to each grocery site and set your delivery location.
# Usage:  ./login.sh              (all sites)
#         ./login.sh blinkit      (one site)
cd "$(dirname "$0")"
source .venv/bin/activate
python3 login.py "$@"
