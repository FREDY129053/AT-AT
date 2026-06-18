FROM python:3.12-bookworm

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# Copy backend sources
COPY ./apps/backend /app

# Install build tools and the package from the local directory.
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir /app \
    && apt-get remove -y --purge && rm -rf /var/lib/apt/lists/*

EXPOSE 8000

# Healthcheck: try /health and fall back to root if /health is not present
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys
try:
    r=urllib.request.urlopen('http://localhost:8000/health')
    sys.exit(0 if r.getcode()==200 else 1)
except Exception:
    try:
        r=urllib.request.urlopen('http://localhost:8000/')
        sys.exit(0 if r.getcode()==200 else 1)
    except Exception:
        sys.exit(1)"

# Start the backend using uvicorn (assumes package exposes FastAPI app at backend.main:app)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
