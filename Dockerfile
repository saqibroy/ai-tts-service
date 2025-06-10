FROM python:3.10-slim-buster

# Prevent Python from writing .pyc files to disc
ENV PYTHONDONTWRITEBYTECODE 1

# Ensure output is sent straight to terminal
ENV PYTHONUNBUFFERED 1

# System dependencies for Coqui TTS and general compilation (best practice)
# We need libssl-dev for Python's SSL module to work correctly with pip via HTTPS
# and build-essential for general compilation of certain Python packages.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libssl-dev \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements.txt
# Using COPY --link for potentially faster builds if requirements.txt changes often
COPY --link requirements.txt .

# Upgrade pip to the latest version as suggested by previous logs
# Then install Python dependencies
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the port your FastAPI application listens on
EXPOSE 8000

# Define the command to run your FastAPI application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]