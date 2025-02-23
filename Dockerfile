# Use Python base image for local development
FROM python:3.9-slim AS base

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy environment files if they exist
COPY .env* ./

# Copy function code
COPY sync.py .
COPY config.py .
COPY scripts ./scripts/

# Create logs directory
RUN mkdir -p logs && chmod 777 logs

# Set environment to docker
ENV ENVIRONMENT=docker

# Default command for local development
CMD ["python", "sync.py"]

# Lambda-specific build
FROM public.ecr.aws/lambda/python:3.9 AS lambda

# Copy requirements.txt
COPY requirements.txt ${LAMBDA_TASK_ROOT}/

# Install the specified packages
RUN pip install -r requirements.txt

# Copy function code
COPY app.py ${LAMBDA_TASK_ROOT}/app.py
COPY sync.py ${LAMBDA_TASK_ROOT}/sync.py
COPY config.py ${LAMBDA_TASK_ROOT}/config.py

# Set environment to aws
ENV ENVIRONMENT=aws

# Set the CMD to your handler
CMD [ "app.lambda_handler" ]
