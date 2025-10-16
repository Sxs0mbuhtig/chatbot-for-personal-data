# Example Dockerfile structure for environment fix
FROM python:3.10-slim

# Install system dependencies (CRITICAL for packages like lxml, chroma-hnswlib, etc.)
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt-dev \
    ... \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the port
EXPOSE 7860

# Define the production startup command (CRITICAL for HF Space)
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "app:app"]