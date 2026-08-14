# Multi-stage build for J.A.D.A Go Agent

# Stage 1: Build the React frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Build the Go backend binary
FROM golang:1.22-alpine AS backend-builder

WORKDIR /app/backend_go

# Copy and install corporate CA certificates for go mod download HTTPS
RUN apk --no-cache add ca-certificates
COPY certificates/*.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates || true

COPY backend_go/ ./
RUN go mod tidy && go mod download
RUN CGO_ENABLED=0 GOOS=linux go build -o /jada-go-server ./cmd/server/main.go

# Stage 3: Final minimal runtime image
FROM alpine:latest

WORKDIR /app

# Install ca-certificates and tzdata
RUN apk --no-cache add ca-certificates tzdata

# Copy and install corporate CA certificates
COPY certificates/*.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates || true

# Copy Go binary from builder
COPY --from=backend-builder /jada-go-server /app/jada-go-server

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/backend/static /app/static

# Create memory store directory
RUN mkdir -p /app/memory_store

EXPOSE 8000

ENV VLLM_BASE_URL=http://172.18.0.2:8000/v1
ENV VLLM_MODEL=/models/Qwen3.5-9B-AWQ
ENV HOST=0.0.0.0
ENV PORT=8000
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

CMD ["/app/jada-go-server"]
