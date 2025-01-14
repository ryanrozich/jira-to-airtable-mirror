FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create volume for logs
VOLUME ["/app/logs"]

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the sync script
ENTRYPOINT ["python", "sync.py"]
CMD ["--schedule"]
