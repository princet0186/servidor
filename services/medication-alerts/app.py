from fastapi import FastAPI

app = FastAPI(title="Medication Alerts Service")

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "medication-alerts"}

@app.get("/api/alerts")
def get_alerts():
    return {"active_alerts": []}
