#!/bin/bash

# Stop Stock Analysis App

echo "🛑 Stopping Stock Analysis App..."

# Kill streamlit processes
pkill -f "streamlit run app.py"

# Check if stopped
if pgrep -f "streamlit run" > /dev/null; then
    echo "❌ Failed to stop app. Trying force kill..."
    pkill -9 -f "streamlit run"
else
    echo "✅ App stopped successfully!"
fi

