#!/bin/bash
set -e

echo "=== Servidor Local Development ==="
echo ""

# Load environment variables
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Kill any existing processes on our ports
echo "Cleaning up stale processes..."
for port in 8000 8001 8002 8003 8004; do
    pid=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$pid" ]; then
        echo "  Killing process on port $port (PID: $pid)"
        kill -9 $pid 2>/dev/null || true
    fi
done
sleep 1

# Activate virtual environment
source venv/bin/activate

# Start all backend services
echo ""
echo "Starting services..."

echo "  → Agent Backend     :8000"
cd agent
uvicorn main:app --host 0.0.0.0 --port 8000 &
cd ..

# One hospital service image, run four times
port=8001
for svc in vitals-ingestion medication-alerts lab-routing patient-portal; do
    echo "  → $svc :$port"
    (cd services/clinical-service && SERVICE_NAME=$svc uvicorn app:app --host 0.0.0.0 --port $port) &
    port=$((port + 1))
done

echo ""
echo "All services started. Frontend: http://localhost:5173"
echo "Press Ctrl+C to stop all services."
echo ""

# Wait for all background processes
trap 'kill $(jobs -p) 2>/dev/null; exit 0' INT TERM
wait
