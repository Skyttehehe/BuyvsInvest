#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  echo "Opretter virtuelt Python-miljø..."
  python3 -m venv .venv
fi

.venv/bin/pip install --quiet -r requirements.txt
echo ""
echo "Starter Bolig vs. Investering på http://127.0.0.1:8000"
echo "På netværket: http://$(ipconfig getifaddr en0 2>/dev/null || echo "<denne-pcs-ip>"):8000"
echo ""
exec .venv/bin/python manage.py runserver 0.0.0.0:8000
