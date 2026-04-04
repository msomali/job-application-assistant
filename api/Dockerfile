FROM python:3.11-slim

WORKDIR /app

# Install core first (dependency)
COPY core/ ./core/
RUN pip install --no-cache-dir ./core

# Install api
COPY api/ ./api/
RUN pip install --no-cache-dir ./api

WORKDIR /app/api
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
