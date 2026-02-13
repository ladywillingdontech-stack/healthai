# Railway-friendly Dockerfile
FROM python:3.11-slim

# Install only essential system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install Rust (minimal)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable --profile minimal
ENV PATH="/root/.cargo/bin:${PATH}"

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with optimizations
# Install setuptools first to ensure pkg_resources is available for packages that need it
# Use setuptools 68.0.0+ which includes pkg_resources by default
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir "setuptools>=68.0.0" "wheel>=0.40.0"
# Install requirements with build isolation disabled to ensure setuptools is available
# This is safe because we're in a controlled Docker environment
RUN pip install --no-cache-dir --no-build-isolation -r requirements.txt

# Copy application code
COPY . .

# Clean up to reduce image size
RUN apt-get remove -y build-essential curl git pkg-config libssl-dev && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /root/.cargo/registry /root/.cargo/git

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose port (Railway will set PORT automatically)
EXPOSE 8000

# Railway will auto-detect and run the app
CMD ["hypercorn", "app.main:app", "--bind", "::"]
