# Use a Python base image
FROM python:3.12-slim

# 1. Install necessary build dependencies as ROOT.
RUN apt-get update && \
    apt-get install -y \
    libxml2-dev \
    libxslt-dev \
    libjpeg-dev \
    zlib1g-dev \
    build-essential \
    gfortran \
    python3-wheel \
    && rm -rf /var/lib/apt/lists/*

# 2. Set the working directory and copy requirements.txt (as root)
WORKDIR /app
COPY requirements.txt .

# 3. Install Python dependencies as ROOT. (System-wide install)
RUN pip install --no-cache-dir -r requirements.txt

# ----------------------------------------------------
# 4. Switch to the non-root user for security and runtime.
# ----------------------------------------------------

# Create the dedicated non-root user
RUN useradd -m -u 1000 user

# Switch to the non-root user
USER user

# Set the PATH environment variable for the non-root user
ENV PATH="/home/user/.local/bin:$PATH"

# 5. Copy the application source code (now owned by 'user')
# The WORKDIR /app is still active and owned by root, but the files copied here 
# will be owned by 'user' when using COPY --chown=user.
COPY --chown=user . /app

# The working directory is already /app from step 2, but setting it again 
# after the final COPY ensures the subsequent CMD executes correctly in /app.
WORKDIR /app

# Expose the port 
EXPOSE 7860

# Define the production startup command using gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:7860", "--workers", "2"]