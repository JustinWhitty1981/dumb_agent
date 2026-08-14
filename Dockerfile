# Multi-stage build for LangChain Agent
# Stage 1: Build the frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Build and run the backend
FROM python:3.11-slim

WORKDIR /app

# Copy and install corporate CA certificates for HTTPS requests
COPY certificates/*.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates

# Install dependencies using pip with SSL verification bypass for PyPI
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.io --trusted-host files.pythonhosted.org -r requirements.txt

# Copy backend source code
COPY backend/ ./

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/backend/static ./backend/static

# Create memory store directory
RUN mkdir -p /app/memory_store

# Expose port
EXPOSE 8000

# Set environment variables for vLLM
ENV VLLM_BASE_URL=http://172.18.0.2:8000/v1
ENV VLLM_MODEL=/models/Qwen3.5-9B-AWQ
ENV HOST=0.0.0.0
ENV PORT=8000

# Configure HTTPS clients to use corporate CA certificates
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Run the application (with conditional SSL support)
CMD ["sh", "-c", "if [ -n \"$SSL_KEYFILE\" ] && [ -n \"$SSL_CERTFILE\" ]; then uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --ssl-keyfile \"$SSL_KEYFILE\" --ssl-certfile \"$SSL_CERTFILE\"; else uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}; fi"]