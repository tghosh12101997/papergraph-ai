#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/../backend"
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp -n ../.env.example .env || true
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
