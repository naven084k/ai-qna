FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    CLOUD_RUN_SERVICE=true

# Expose the port
EXPOSE 8501

# Set up a non-root user
RUN useradd -m appuser
USER appuser

# Command to run the application with support for headless mode
# Use HEADLESS=true environment variable to run in headless mode
ENTRYPOINT ["sh", "-c", "if [ \"$HEADLESS\" = \"true\" ]; then python app.py --headless; else streamlit run app.py --server.port=8501 --server.address=0.0.0.0; fi"]
