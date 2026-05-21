from fastapi import FastAPI
import random
import time

app = FastAPI(title="Vitals Ingestion Service")

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "vitals-ingestion"}

@app.get("/api/vitals")
def get_vitals():
    # Simulate processing delay
    time.sleep(0.05)
    return {
        "heart_rate": random.randint(60, 100),
        "blood_pressure": f"{random.randint(110, 130)}/{random.randint(70, 90)}",
        "oxygen_level": random.randint(95, 100)
    }

@app.post("/api/simulate_failure")
def simulate_failure():
    # We will use this later to trigger the failure scenario for the demo
    return {"status": "failure_triggered", "description": "Memory pressure increasing"}
