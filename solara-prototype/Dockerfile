# Hugging Face Spaces - Solara Dashboard
# HTYPE Geographic Intelligence Dashboard

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for geospatial libraries
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port 7860 (Hugging Face Spaces default)
EXPOSE 7860

# Run Solara on port 7860
CMD ["solara", "run", "app.py", "--host", "0.0.0.0", "--port", "7860"]
