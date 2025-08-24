FROM python:3.11-slim
WORKDIR /SYNB_assignment


# 3. Install system packages needed by Python libraries
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    pkg-config \
    libcairo2-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# 4. Copy requirements.txt first (for Docker caching efficiency)
COPY requirements.txt .

# 5. Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy your application code
COPY Assignment_SYNB.py .

# 7. Create directory for database and exports
RUN mkdir -p /SYNB_assignment/data /SYNB_assignment/exports

# 8. Set environment variables
ENV FLASK_APP=Assignment_SYNB.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# 9. Expose port 5000 (tell Docker our app uses this port)
EXPOSE 5000

# 10. Health check - Docker will test if container is working
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# 11. Command to run when container starts
CMD ["python", "Assignment_SYNB.py"]