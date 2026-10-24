#!/bin/bash
set -e

BASE_URL="http://localhost:8000/api/v1"

echo "=== Servidor API E2E Test ==="

echo "1. Checking Health..."
curl -s http://localhost:8000/health | grep "healthy" && echo "✅ Health OK"

echo "2. Checking Current Status..."
curl -s "$BASE_URL/status" | grep "services" && echo "✅ Status OK"

echo "3. Injecting a real fault into vitals-ingestion (memory_pressure)..."
curl -s -X POST "$BASE_URL/simulate/failure" -H "Content-Type: application/json" -d '{"service":"vitals-ingestion","failure_type":"memory_pressure","severity":"high"}'
echo

echo "Waiting for the agent's live probes to detect it and plan (up to 120s)..."
INCIDENT_ID=""
for i in $(seq 1 60); do
    STATUS=$(curl -s "$BASE_URL/status")
    if echo "$STATUS" | grep -q '"incident_status":"plan_ready"'; then
        INCIDENT_ID=$(echo "$STATUS" | grep -o '"active_incident":"[^"]*' | cut -d'"' -f4)
        break
    fi
    sleep 2
done

if [ -z "$INCIDENT_ID" ]; then
    echo "❌ Agent did not open and plan an incident"
    exit 1
fi

echo "✅ Incident detected and planned: $INCIDENT_ID"

echo "4. Fetching Incident Details..."
curl -s "$BASE_URL/incidents/$INCIDENT_ID" > incident.json
cat incident.json | grep "blast_radius" && echo "✅ Incident data retrieved"

echo "5. Checking Briefings..."
curl -s "$BASE_URL/incidents/$INCIDENT_ID/briefings" | grep "physician" && echo "✅ Briefings found"

echo "6. Checking Notifications..."
curl -s "$BASE_URL/incidents/$INCIDENT_ID/notifications" | grep "recipient_name" && echo "✅ Notifications generated"

echo "7. Approving the steps the agent is waiting on..."
for STEP in $(curl -s "$BASE_URL/incidents/$INCIDENT_ID" | python3 -c "
import sys, json
plan = json.load(sys.stdin)['remediation_plan']
print(' '.join(str(s['order']) for s in plan if s['status'] == 'pending' and s['risk_level'] in ('MEDIUM', 'HIGH')))"); do
    curl -s -X POST "$BASE_URL/incidents/$INCIDENT_ID/approve/$STEP" && echo " ✅ Step $STEP approved"
done

echo "Waiting for verified recovery (up to 120s)..."
for i in $(seq 1 60); do
    curl -s "$BASE_URL/incidents/$INCIDENT_ID" | grep -q '"status":"resolved"' && break
    sleep 2
done
sleep 5

echo "8. Checking Compliance Report..."
curl -s "$BASE_URL/incidents/$INCIDENT_ID/compliance" | grep "narrative" && echo "✅ Compliance report generated"

echo "9. Resetting Incident..."
curl -s -X POST "$BASE_URL/incidents/$INCIDENT_ID/reset" && echo "✅ Incident reset"

echo "=== All Tests Completed Successfully! ==="
