from fastapi import FastAPI

app = FastAPI(title="Lab Routing Service")

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "lab-routing"}

@app.get("/api/labs")
def get_labs():
    return {"pending_results": 0}
