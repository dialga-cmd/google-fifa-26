FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . /app

# Expose port; Render sets $PORT at runtime
EXPOSE 10000

# Run using uvicorn. Use shell form so $PORT is expanded at runtime.
CMD sh -c "uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers"
