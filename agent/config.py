import os

AGENT_PORT = int(os.getenv("AGENT_PORT", "8000"))
DYNATRACE_URL = os.getenv("DYNATRACE_URL", "http://localhost:9999")
DYNATRACE_TOKEN = os.getenv("DYNATRACE_TOKEN", "")
GCP_PROJECT = os.getenv("GCP_PROJECT", "servidor-hackathon")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
