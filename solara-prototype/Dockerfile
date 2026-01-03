# Hugging Face Spaces - Solara Dashboard
# HTYPE Geographic Intelligence Dashboard
#
# Uses jupyter/base-notebook for proper ipywidgets/ipyleaflet support

FROM jupyter/base-notebook:latest

# Switch to root for package installation
USER root

# Set working directory
WORKDIR /app

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Fix permissions for jovyan user (Jupyter notebook default)
RUN chown -R ${NB_UID}:${NB_GID} /app

# Switch back to notebook user
USER ${NB_USER}

# Expose port 8765 (Solara default)
EXPOSE 8765

# Run Solara on port 8765
CMD ["solara", "run", "app.py", "--host", "0.0.0.0", "--port", "8765"]
