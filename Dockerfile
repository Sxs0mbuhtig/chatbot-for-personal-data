# Use a Python base image
FROM python:3.10-slim

# Install system dependencies needed for lxml, pdf2image, and chroma-hnswlib
# We also include 'gfortran' and 'build-essential' for packages that require compilation
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt-dev \
    libjpeg-dev \
    zlib1g-dev \
    gfortran \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# --- Hugging Face User Setup (CRITICAL) ---
# Create a dedicated non-root user
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Set working directory and change ownership
WORKDIR /app

# Copy requirements and install Python packages, ensuring the user owns them
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code, ensuring the user owns it
COPY --chown=user . /app

# Expose the port (standard for HF Spaces)
EXPOSE 7860

# Define the production startup command using gunicorn (best for Flask)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]