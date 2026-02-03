FROM python:3.11-bullseye

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Install Playwright browsers (will be run in postCreateCommand as well, but good to have)
RUN pip install playwright && \
    playwright install --with-deps

# Keep container running
CMD ["sleep", "infinity"]
