#!/bin/bash
# PetroLedger Backend Starter
# Double-click this file in Finder to start the backend server automatically.

# Move to the script's directory and then to the backend folder
cd "$(dirname "$0")/backend"

echo "=========================================================="
echo "Starting PetroLedger Backend Server..."
echo "=========================================================="

# Activate the virtual environment
if [ -d ".venv" ]; then
    echo "Activating virtual environment (.venv)..."
    source .venv/bin/activate
else
    echo "ERROR: Virtual environment (.venv) not found!"
    echo "Please make sure you have run the setup instructions."
    read -p "Press Enter to exit..."
    exit 1
fi

# Run Alembic migrations
echo "Running database migrations..."
alembic upgrade head

# Start the server
echo "Starting Uvicorn server on http://127.0.0.1:8000..."
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
