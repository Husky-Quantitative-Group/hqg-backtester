#!/bin/bash

# Build the Docker worker image for sandboxed backtest execution

echo "Building backtester-worker Docker image..."
docker build -f api/Dockerfile.worker -t backtester-worker .

if [ $? -eq 0 ]; then
    echo "✓ Worker image built successfully!"
    echo ""
    echo "The API will now use Docker sandboxing for backtest execution."
    echo "Security features enabled:"
    echo "  - No network access"
    echo "  - Read-only filesystem"
    echo "  - Resource limits (CPU, memory, PIDs)"
    echo "  - Dropped Linux capabilities"
    echo "  - Non-root user execution"
else
    echo "✗ Build failed!"
    exit 1
fi
