# Use a specific and stable base image
FROM python:3.10-slim-buster

# Prevent Python from writing .pyc files to disc for a leaner image
ENV PYTHONDONTWRITEBYTECODE 1

# Ensure Python's stdout/stderr is immediately flushed for real-time logging
ENV PYTHONUNBUFFERED 1

# --- System Dependencies for Building and Runtime ---
# This layer installs essential build tools, OpenSSL development libraries,
# and ffmpeg for audio processing.
# The `libffi-dev` package is often required for certain cryptography-related
# Python packages that might get pulled in by your dependencies.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libssl-dev \
        libffi-dev \
        ffmpeg \
    # Clean up apt cache to keep image size small
    && rm -rf /var/lib/apt/lists/*

# Set working directory for the application
WORKDIR /app

# Copy requirements.txt first to leverage Docker's build cache
COPY --link requirements.txt .

# --- Python Environment Setup and Dependency Installation ---
# Upgrade pip to the latest version. This is critical as older pip versions
# can sometimes struggle with modern dependency resolution or SSL handling.
# Then, install all Python dependencies.
# We also include 'setuptools' and 'wheel' as they are often implicit
# dependencies for complex package installations (like those with C extensions).
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Expose the port your FastAPI application listens on
EXPOSE 8000

# Define the command to run your FastAPI application using Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]