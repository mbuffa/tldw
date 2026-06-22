#!/bin/sh
set -e
if [ ! -d .venv ]; then
  python3.13 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
