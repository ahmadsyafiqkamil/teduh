# TEDUH API image.
#
# Data artifacts are COPYed into the image rather than fetched from GCS at startup. They
# total about 9 MB, which is far too small to justify a network dependency plus credentials
# plus download-failure handling on the critical path during judging. See docs/DECISIONS.md.
#
# WeasyPrint renders the policy brief PDF and needs Pango/Cairo as system libraries; pip
# cannot supply those, which is why this is a slim image with apt packages and not distroless.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# libgomp1 is the GNU OpenMP runtime that LightGBM's native library links against; without
# it, `import lightgbm` fails at runtime with "libgomp.so.1: cannot open shared object file".
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        libgomp1 \
        shared-mime-info \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first so a code change does not invalidate the dependency layer.
# --no-group pipeline keeps earthengine-api, rasterio and geopandas out of the runtime
# image (CLAUDE.md rule 6): Earth Engine is never called at request time.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-group pipeline

COPY teduh_agent/ teduh_agent/
COPY model/ model/
COPY api/ api/
COPY config/ config/
COPY data/boundaries/ data/boundaries/
COPY data/processed/ data/processed/
COPY data/evidence/ data/evidence/
COPY data/model/ data/model/

ENV PATH="/app/.venv/bin:$PATH" \
    PORT=8080

EXPOSE 8080

# Cloud Run injects PORT, so it is expanded at runtime by the shell rather than baked in.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
