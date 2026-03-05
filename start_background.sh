#!/bin/bash

# Stock Analysis App - Background Launcher
# Run this to start the app in the background

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Navigate to the app directory
cd "$DIR"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Kill any existing streamlit processes on port 8501
lsof -ti:8501 | xargs kill -9 2>/dev/null

# Start Streamlit app in background
echo "🚀 Starting Stock Analysis App in background..."
nohup streamlit run app.py \
    --server.port=8501 \
    --server.address=localhost \
    --browser.gatherUsageStats=false \
    --server.headless=false > /tmp/stockanalysis.log 2>&1 &

# Wait for app to start
sleep 3

# Open in browser
echo "✅ App started successfully!"
echo "🔗 Opening in browser: http://localhost:8501"
echo "📋 Logs: /tmp/stockanalysis.log"
echo ""
echo "To stop the app, run: pkill -f 'streamlit run'"

# Open browser
open http://localhost:8501

