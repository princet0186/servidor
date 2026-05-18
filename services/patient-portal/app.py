from fastapi import FastAPI

app = FastAPI(title="Patient Portal Service")

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "patient-portal"}

@app.get("/api/portal/status")
def get_status():
    return {"active_sessions": 42}
