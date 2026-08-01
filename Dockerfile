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

# Install uv for faster dependency resolution
RUN pip install --no-cache-dir uv

# Copy requirements and install with uv (faster, more deterministic)
COPY backend/requirements.txt ./
RUN uv pip install --system --no-cache -r requirements.txt

# Copy backend source code
COPY backend/ ./

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/backend/static ./backend/static

# Create memory store directory
RUN mkdir -p /app/memory_store

# Expose port
EXPOSE 8000

# Set environment variables
ENV OLLAMA_BASE_URL=http://192.168.0.59:11434
ENV OLLAMA_MODEL=qwen3.5:9b
ENV HOST=0.0.0.0
ENV PORT=8000

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]