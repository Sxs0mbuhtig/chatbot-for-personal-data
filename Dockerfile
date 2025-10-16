# Start with a slightly newer, yet stable, Python version
FROM python:3.11 

# --- HF Recommended Security/User Setup ---
# Create a dedicated, non-root user (best security practice)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Set working directory
WORKDIR /app

# --- Dependency Installation (The Fix) ---
# Install system dependencies (needed for lxml and other C-packages)
# Add this section back, which was missing in both your initial attempt and the HF template!
RUN apt-get update && \
    apt-get install -y build-essential libxml2-dev libxslt-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install Python dependencies
COPY --chown=user ./requirements.txt requirements.txt
# Use --upgrade to help resolve those dependency conflicts you saw earlier
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy the rest of your application code
COPY --chown=user . /app

# --- Application Startup (The Entry Point) ---
# NOTE: You MUST confirm the correct command for your app.
# The default HF command is for Uvicorn (FastAPI/Starlette).
# If your app uses Flask or Gradio, you need a different CMD.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]