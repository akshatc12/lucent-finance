#!/bin/bash
# Lucent — double-click me in Finder to launch.
#
# Finds a free port automatically (no more clashes with AirPlay on :5000 or a
# stale instance) and opens your browser to the dashboard. Close this Terminal
# window to stop the app. First launch may need: right-click → Open (Gatekeeper).
cd "$(dirname "$0")" || exit 1
export LUCENT_OPEN=1
echo "Starting Lucent…  (close this window to stop)"
exec uv run --with-requirements requirements.txt app.py
