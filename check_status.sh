#!/bin/bash

# Check Stock Analysis App Status

echo "🔍 Checking Stock Analysis App Status..."
echo ""

# Check if process is running
if pgrep -f "streamlit run app.py" > /dev/null; then
    echo "✅ App is RUNNING"
    echo ""
    
    # Get process info
    echo "📊 Process Info:"
    ps aux | grep "streamlit run app.py" | grep -v grep
    echo ""
    
    # Check port
    echo "🔌 Port Status:"
    lsof -i:8501
    echo ""
    
    echo "🔗 Access URL: http://localhost:8501"
    echo "📋 Logs: /tmp/stockanalysis.log"
    echo ""
    echo "To stop: ./stop_app.sh"
else
    echo "❌ App is NOT running"
    echo ""
    echo "To start: ./start_app.sh (foreground)"
    echo "       or ./start_background.sh (background)"
fi

