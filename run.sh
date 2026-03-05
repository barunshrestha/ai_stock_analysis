#!/usr/bin/env bash
cd "$(dirname "$0")"
if [ -d ".venv" ]; then
  .venv/bin/python -m streamlit run app.py
else
  python3 -m streamlit run app.py
fi
