# Solara Dashboard - HTYPE Geographic Intelligence
# Uses jupyter/base-notebook for proper ipywidgets/ipyleaflet support
# Compatible with Render.com, HF Spaces, and other Docker hosts

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

# Default port (can be overridden by PORT env var)
ENV PORT=8765
EXPOSE 8765

# Run Solara - uses PORT env var for flexibility across platforms
CMD solara run app.py --host 0.0.0.0 --port ${PORT}
