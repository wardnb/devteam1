FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create workspace directories
RUN mkdir -p workspace/tests workspace/designs logs data

ENV PYTHONPATH=/app
ENV OLLAMA_HOST=http://ollama:11434

CMD ["python", "main.py"]