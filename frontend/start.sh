#!/bin/bash

# Neshama Frontend Startup Script
# Starts the API server and opens the frontend in browser

echo "======================================================================"
echo " STARTING NESHAMA"
echo "======================================================================"
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

# Check if database exists
DB_PATH="../neshama_backend/neshama.db"
if [ ! -f "$DB_PATH" ]; then
    DB_PATH="$HOME/Desktop/Neshama/neshama.db"
fi

if [ ! -f "$DB_PATH" ]; then
    echo "⚠️  Database not found!"
    echo ""
    echo "Please ensure the backend scrapers have run at least once."
    echo "Expected location: ~/Desktop/Neshama/neshama.db"
    echo ""
    exit 1
fi

echo "✅ Database found: $DB_PATH"
echo ""

# Start API server in background
echo "Starting API server..."
python3 api_server.py &
API_PID=$!

# Give server time to start
sleep 2

# Open browser
echo ""
echo "Opening Neshama in your browser..."
if command -v open &> /dev/null; then
    # macOS
    open "https://neshama.ca" 2>/dev/null || open index.html
elif command -v xdg-open &> /dev/null; then
    # Linux
    xdg-open index.html
else
    echo "Please open index.html in your browser manually"
fi

echo ""
echo "======================================================================"
echo " NESHAMA IS RUNNING"
echo "======================================================================"
echo ""
echo " Frontend: https://neshama.ca (or open index.html)"
echo " API:      https://neshama.ca/api/obituaries"
echo ""
echo " Press Ctrl+C to stop the server"
echo "======================================================================"
echo ""

# Wait for API server
wait $API_PID
