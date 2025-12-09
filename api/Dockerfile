FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY api/requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backtester package
COPY backtester/ /app/backtester/

# Copy the API main file
COPY api/main.py /app/main.py

# Set PYTHONPATH
ENV PYTHONPATH="/app"

# Expose port
EXPOSE 8000

# Run the FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
