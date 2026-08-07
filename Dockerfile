FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .
COPY openapi.json .
# listener.py and mcp_dispatcher.py import agents.*; scripts/ holds the
# JSON->SQL migration documented in README.md and docs/DEPLOYMENT.md.
COPY agents/ ./agents/
COPY scripts/ ./scripts/

# Default command (overridden per service in docker-compose)
CMD ["sh", "-lc", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
