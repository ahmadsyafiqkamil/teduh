#!/usr/bin/env bash
# Build and deploy teduh-web.
#
# Resolves the API URL from the deployed Cloud Run service rather than taking it as an
# argument, because a frontend built against the wrong API URL fails as an empty map with no
# error message -- the worst possible failure during judging.
set -euo pipefail

PROJECT="${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT belum diisi}"
REGION="${GOOGLE_CLOUD_LOCATION:-asia-southeast2}"
WEB_REGION="${TEDUH_WEB_REGION:-asia-southeast1}"
API_SERVICE="teduh-api"
WEB_SERVICE="teduh-web"
REPO="teduh"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_URL="$(gcloud run services describe "$API_SERVICE" \
  --project "$PROJECT" --region "$REGION" --format 'value(status.url)' 2>/dev/null || true)"

if [[ -z "$API_URL" ]]; then
  echo "GAGAL: layanan $API_SERVICE belum ada di $REGION." >&2
  echo "Jalankan ./infra/deploy_api.sh lebih dulu." >&2
  exit 1
fi
echo "==> API: $API_URL"

# Fail now rather than shipping a frontend that cannot reach its data.
if ! curl -fsS "${API_URL}/api/health" > /dev/null; then
  echo "GAGAL: ${API_URL}/api/health tidak menjawab." >&2
  exit 1
fi

cd web

IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${WEB_SERVICE}:$(date +%Y%m%d-%H%M%S)"

gcloud builds submit . \
  --project "$PROJECT" \
  --config cloudbuild.yaml \
  --substitutions "_IMAGE=${IMAGE},_API_URL=${API_URL}"

gcloud run deploy "$WEB_SERVICE" \
  --project "$PROJECT" \
  --region "$WEB_REGION" \
  --image "$IMAGE" \
  --allow-unauthenticated \
  --memory 512Mi \
  --min-instances "${TEDUH_MIN_INSTANCES:-0}" \
  --max-instances 4 \
  --set-env-vars "NEXT_PUBLIC_TEDUH_API=${API_URL}"

WEB_URL="$(gcloud run services describe "$WEB_SERVICE" \
  --project "$PROJECT" --region "$WEB_REGION" --format 'value(status.url)')"

echo "==> web: $WEB_URL"
echo
echo "LANGKAH TERAKHIR: izinkan origin ini di API, kalau tidak browser akan memblokir"
echo "semua permintaan dan petanya tampil kosong tanpa pesan error:"
echo "  TEDUH_WEB_ORIGIN=${WEB_URL} ./infra/deploy_api.sh"
