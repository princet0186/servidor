#!/usr/bin/env bash
# Deploy Servidor to Google Cloud Run: four hospital services plus the ADK agent.
#
#   ./deploy/cloudrun.sh <gcp-project-id> [region]
#
# Reads secrets (Gemini keys, MongoDB, SMTP, Dynatrace) from .env. Every service is capped at
# one instance, so demo usage stays inside Cloud Run's free tier.
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT="${1:?usage: deploy/cloudrun.sh <gcp-project-id> [region]}"
REGION="${2:-us-central1}"
REPO=servidor
AR="$REGION-docker.pkg.dev/$PROJECT/$REPO"
AGENT_SA="servidor-agent@$PROJECT.iam.gserviceaccount.com"
SERVICES=(vitals-ingestion medication-alerts lab-routing patient-portal)
ADMIN_TOKEN="$(openssl rand -hex 16)"

echo "==> Project $PROJECT, region $REGION"
gcloud config set project "$PROJECT" >/dev/null
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com

if ! gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1; then
    gcloud artifacts repositories create "$REPO" --repository-format=docker --location "$REGION"
fi

echo "==> Building the hospital service image"
gcloud builds submit services/clinical-service --tag "$AR/clinical-service:latest"

URL_LINES=""
for svc in "${SERVICES[@]}"; do
    echo "==> Deploying $svc (stable release)"
    gcloud run deploy "$svc" --image "$AR/clinical-service:latest" --region "$REGION" \
        --allow-unauthenticated --max-instances 1 --memory 512Mi --cpu 1 \
        --set-env-vars "SERVICE_NAME=$svc,RELEASE_VERSION=v2.4.0,SERVICE_ADMIN_TOKEN=$ADMIN_TOKEN" --quiet
    # A previous rollback may have pinned traffic to an old revision
    gcloud run services update-traffic "$svc" --region "$REGION" --to-latest --quiet >/dev/null
    url="$(gcloud run services describe "$svc" --region "$REGION" --format 'value(status.url)')"
    URL_LINES="$URL_LINES$svc=$url"$'\n'
done

echo "==> Service account for the agent (may deploy revisions and route traffic)"
if ! gcloud iam service-accounts describe "$AGENT_SA" >/dev/null 2>&1; then
    gcloud iam service-accounts create servidor-agent --display-name "Servidor ADK agent"
fi
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format 'value(projectNumber)')"
RUNTIME_SA="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:$AGENT_SA" \
    --role roles/run.developer --condition None --quiet >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:$AGENT_SA" \
    --role roles/aiplatform.user --condition None --quiet >/dev/null
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" --member "serviceAccount:$AGENT_SA" \
    --role roles/iam.serviceAccountUser --quiet >/dev/null

echo "==> Building the agent image"
gcloud builds submit --config deploy/cloudbuild.agent.yaml --substitutions "_IMAGE=$AR/servidor-agent:latest" .

ENV_FILE="$(mktemp)"
trap 'rm -f "$ENV_FILE"' EXIT
URL_LINES="$URL_LINES" python3 - "$ENV_FILE" <<EOF
import json, os, sys
urls = dict(l.split("=", 1) for l in os.environ["URL_LINES"].splitlines() if l)
keep = {"GOOGLE_API_KEY", "GEMINI_MODEL", "ADK_MODEL", "MONGODB_URI", "MONGODB_DB", "DYNATRACE_URL",
        "DYNATRACE_TOKEN", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "NOTIFY_EMAIL_FROM",
        "NOTIFY_EMAIL_TO", "FRONTEND_URL", "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_CLOUD_LOCATION"}
env = {}
for line in open(".env"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip("\"'")
        if k in keep or k.startswith("GEMINI_API_KEY_"):
            env[k] = v
env.update({
    "CLOUD_RUN_ENABLED": "true", "GCP_PROJECT": "$PROJECT", "CLOUD_RUN_REGION": "$REGION",
    "SERVICE_ADMIN_TOKEN": "$ADMIN_TOKEN", "MONITOR_INTERVAL": "5",
    "VITALS_INGESTION_URL": urls["vitals-ingestion"],
    "MEDICATION_ALERTS_URL": urls["medication-alerts"],
    "LAB_ROUTING_URL": urls["lab-routing"],
    "PATIENT_PORTAL_URL": urls["patient-portal"],
})
with open(sys.argv[1], "w") as f:
    for k, v in env.items():
        f.write(f"{k}: {json.dumps(v)}\n")
EOF

echo "==> Deploying the agent"
# --no-cpu-throttling keeps the monitor and agent running between requests while an instance is up.
gcloud run deploy servidor-agent --image "$AR/servidor-agent:latest" --region "$REGION" \
    --service-account "$AGENT_SA" --allow-unauthenticated \
    --no-cpu-throttling --min-instances 0 --max-instances 1 --timeout 3600 \
    --memory 1Gi --cpu 1 --env-vars-file "$ENV_FILE" --quiet

AGENT_URL="$(gcloud run services describe servidor-agent --region "$REGION" --format 'value(status.url)')"
echo
echo "Done."
echo "  Agent API:   $AGENT_URL/api/v1/config/status"
printf '%s' "$URL_LINES" | sed 's/=/: /; s/$/\/health/; s/^/  /'
echo
echo "Next: set VITE_API_URL=$AGENT_URL in Vercel and redeploy the frontend,"
echo "then put the Vercel URL in .env as FRONTEND_URL and re-run this script (or update the env var in Cloud Run)."
