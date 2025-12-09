#!/bin/bash
cd ..
docker build -f api/Dockerfile -t hqg-backtester-api .
echo "Built image: hqg-backtester-api"
echo "Run with: docker-compose up"