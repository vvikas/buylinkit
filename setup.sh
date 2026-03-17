#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "Setting up buylinkit..."
python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
playwright install chromium

echo ""
echo "✅ Done! Next steps:"
echo "  cp .env.example .env"
echo "  # add your GROQ_API_KEY to .env"
echo "  ./run.sh 'onions 1kg'"
