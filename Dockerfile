FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application codebase
COPY . .

# Install uvicorn wrapper to safely handle unexpanded CLI variables like --port ${PORT:-8000}
RUN cp scripts/uvicorn_wrapper.py /usr/local/bin/uvicorn && chmod +x /usr/local/bin/uvicorn

# Ensure data and log directories exist and keep a seed copy for fresh volume mounts
RUN mkdir -p data/raw data/cleaned data/enriched data/classified data/pulses data/metrics logs && \
    cp -r data data_seed

# Default port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, os; p = os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{p}/api/status')" || exit 1

# Start web dashboard and API via run_web.py (handles dynamic $PORT automatically)
CMD ["python", "run_web.py"]
