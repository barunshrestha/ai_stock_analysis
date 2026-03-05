#!/bin/bash

# Stock Analysis App Launcher
# This script starts the Streamlit app on your local machine

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Navigate to the app directory
cd "$DIR"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start Streamlit app
echo "🚀 Starting Stock Analysis App..."
echo "📊 The app will open in your default browser"
echo "🔗 Bookmark this URL: http://localhost:8501"
echo ""
echo "⚠️  To stop the app, press Ctrl+C in this terminal"
echo ""

# Run streamlit with specific port and settings
streamlit run app.py \
    --server.port=8501 \
    --server.address=localhost \
    --browser.gatherUsageStats=false \
    --server.headless=false

