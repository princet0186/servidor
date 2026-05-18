from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from streaming import router as streaming_router
from detection import check_anomalies

app = FastAPI(title="Servidor Agent Core")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(streaming_router)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "agent-core"}

@app.get("/api/v1/status")
def get_status():
    # In a real scenario, this would query Dynatrace MCP
    # For now, we mock the anomaly detection based on our trigger
    anomalies = check_anomalies()
    return {
        "vitals_ingestion": "error" if anomalies else "healthy",
        "medication_alerts": "healthy",
        "lab_routing": "healthy",
        "patient_portal": "healthy",
        "active_anomalies": anomalies
    }

@app.post("/api/v1/simulate/failure")
def trigger_failure():
    # Set a flag to simulate a Dynatrace anomaly
    with open("/tmp/simulated_failure.flag", "w") as f:
        f.write("active")
    return {"status": "failure_simulated", "message": "Memory pressure on vitals-ingestion simulated."}
