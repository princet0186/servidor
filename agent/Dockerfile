FROM python:3.12-slim
# Build context is the repo root so the clinical seed data in data/ ships with the image
# (database.py resolves it as ../data relative to the agent package).
WORKDIR /app/agent
COPY agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agent/ .
COPY data/ /app/data/
# Use PORT env variable for production (Railway automatically assigns this)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
