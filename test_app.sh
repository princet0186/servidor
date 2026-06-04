#!/bin/bash
set -e

BASE_URL="http://localhost:8000/api/v1"

echo "=== Servidor API E2E Test ==="

echo "1. Checking Health..."
curl -s http://localhost:8000/health | grep "healthy" && echo "✅ Health OK"

echo "2. Checking Current Status..."
curl -s "$BASE_URL/status" | grep "services" && echo "✅ Status OK"

echo "3. Simulating Failure on vitals-ingestion (memory_pressure)..."
SIMULATE_RES=$(curl -s -X POST "$BASE_URL/simulate/failure" -H "Content-Type: application/json" -d '{"service":"vitals-ingestion","failure_type":"memory_pressure","severity":"high"}')
echo $SIMULATE_RES
INCIDENT_ID=$(echo $SIMULATE_RES | grep -o '"incident_id":"[^"]*' | cut -d'"' -f4)

if [ -z "$INCIDENT_ID" ] || [ "$INCIDENT_ID" == "null" ]; then
    echo "❌ Failed to get incident_id"
    exit 1
fi

echo "✅ Simulation Triggered. Incident ID: $INCIDENT_ID"

echo "Waiting for Agent Pipeline to process (15s)..."
sleep 15

echo "4. Fetching Incident Details..."
curl -s "$BASE_URL/incidents/$INCIDENT_ID" > incident.json
cat incident.json | grep "blast_radius" && echo "✅ Incident data retrieved"

echo "5. Checking Briefings..."
curl -s "$BASE_URL/incidents/$INCIDENT_ID/briefings" | grep "physician" && echo "✅ Briefings found"

echo "6. Checking Notifications..."
curl -s "$BASE_URL/incidents/$INCIDENT_ID/notifications" | grep "recipient_name" && echo "✅ Notifications generated"

echo "7. Approving Remediation Steps..."
# We will approve step 3 (MEDIUM risk in static plan)
curl -s -X POST "$BASE_URL/incidents/$INCIDENT_ID/approve/3" && echo "✅ Step 3 approved"

echo "Waiting for resolution (10s)..."
sleep 10

echo "8. Checking Compliance Report..."
curl -s "$BASE_URL/incidents/$INCIDENT_ID/compliance" | grep "narrative" && echo "✅ Compliance report generated"

echo "9. Resetting Incident..."
curl -s -X POST "$BASE_URL/incidents/$INCIDENT_ID/reset" && echo "✅ Incident reset"

echo "=== All Tests Completed Successfully! ==="
