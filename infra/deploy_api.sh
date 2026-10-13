#!/usr/bin/env bash
# Build and deploy teduh-api to Cloud Run.
#
# Fails fast when a data artifact is missing, because the image bakes artifacts in
# (docs/DECISIONS.md) and a deploy that silently ships an image without grid_features would
# only surface as a 500 during judging.
set -euo pipefail

PROJECT="${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT belum diisi}"
REGION="${GOOGLE_CLOUD_LOCATION:-asia-southeast2}"
SERVICE="teduh-api"
REPO="teduh"
MIN_INSTANCES="${TEDUH_MIN_INSTANCES:-0}"
MODEL="${TEDUH_MODEL:-gemini-2.5-flash}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REQUIRED_ARTIFACTS=(
  "data/processed/kelurahan_metrics.parquet"
  "data/processed/grid_features.parquet"
  "data/boundaries/kelurahan.geojson"
  "data/evidence/interventions.json"
  "config/scenario.yaml"
  "config/costs.yaml"
  "config/hvi.yaml"
)

for artifact in "${REQUIRED_ARTIFACTS[@]}"; do
  if [[ ! -f "$artifact" ]]; then
    echo "GAGAL: $artifact tidak ada." >&2
    echo "Jalankan dulu: uv run python -m pipeline.build_grid && uv run python -m pipeline.aggregate_kelurahan" >&2
    exit 1
  fi
done

if [[ ! -f "data/model/model.txt" ]]; then
  echo "PERINGATAN: data/model/model.txt tidak ada. Tool skenario akan menolak melayani." >&2
  echo "Jalankan: uv run python -m model.train" >&2
fi

# Resolve the web origin when it is not supplied explicitly. Deploying the API without an
# origin used to WIPE the value to empty and CORS-block the browser (blank map, no error),
# so this defaults to the live web URLs instead of leaving the guard off by accident.
if [[ -z "${TEDUH_WEB_ORIGIN:-}" ]]; then
  WEB_LEGACY="$(gcloud run services describe teduh-web \
    --project "$PROJECT" --region "$REGION" --format 'value(status.url)' 2>/dev/null || true)"
  # Canonical URL: <service>-<project-number>.<region>.run.app. Derive it from the project
  # number so both the legacy and canonical origins are allowed.
  PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format 'value(projectNumber)' 2>/dev/null || true)"
  ORIGINS=()
  [[ -n "$WEB_LEGACY" ]] && ORIGINS+=("$WEB_LEGACY")
  [[ -n "$PROJECT_NUMBER" ]] && ORIGINS+=("https://teduh-web-${PROJECT_NUMBER}.${REGION}.run.app")
  WEB_ORIGIN="$(IFS=,; echo "${ORIGINS[*]}")"
else
  WEB_ORIGIN="$TEDUH_WEB_ORIGIN"
fi
echo "==> TEDUH_WEB_ORIGIN: ${WEB_ORIGIN:-'(kosong)'}"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${SERVICE}:$(date +%Y%m%d-%H%M%S)"

# Idempotent: succeeds quietly when the repository already exists.
gcloud artifacts repositories create "$REPO" \
  --project "$PROJECT" --location "$REGION" --repository-format docker \
  --description "TEDUH container images" 2>/dev/null || true

echo "==> build $IMAGE"
gcloud builds submit "$ROOT" \
  --project "$PROJECT" \
  --config infra/cloudbuild.yaml \
  --substitutions "_IMAGE=${IMAGE}"

echo "==> deploy $SERVICE ke $REGION"
# gcloud parses --set-env-vars as a comma-separated dict, so a comma INSIDE a value (the
# comma-joined origin list) breaks it. Use an alternate delimiter (^|^) so the commas in
# TEDUH_WEB_ORIGIN are literal. "|" appears in none of the values.
gcloud run deploy "$SERVICE" \
  --project "$PROJECT" \
  --region "$REGION" \
  --image "$IMAGE" \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --concurrency 20 \
  --min-instances "$MIN_INSTANCES" \
  --max-instances 4 \
  --set-env-vars "^|^GOOGLE_CLOUD_PROJECT=${PROJECT}|GOOGLE_CLOUD_LOCATION=${REGION}|GOOGLE_GENAI_USE_ENTERPRISE=True|TEDUH_MODEL=${MODEL}|TEDUH_WEB_ORIGIN=${WEB_ORIGIN}"

URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format 'value(status.url)')"
echo "==> selesai: $URL"
