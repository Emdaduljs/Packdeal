# Dockerfile - Ubuntu based minimal container for Streamlit + CairoSVG
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONUNBUFFERED=1

# Install system packages and Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    pkg-config \
    libcairo2 \
    libcairo2-dev \
    libpango-1.0-0 \
    libpango1.0-dev \
    libgdk-pixbuf2.0-0 \
    libgdk-pixbuf2.0-dev \
    libffi-dev \
    shared-mime-info \
    ca-certificates \
    git \
    fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

# (Optional) If you want Inkscape to outline text server-side, uncomment:
# RUN apt-get update && apt-get install -y --no-install-recommends inkscape && rm -rf /var/lib/apt/lists/*

# Create app dir and copy requirements
WORKDIR /app
COPY requirements.txt .

# Upgrade pip, build wheels if needed, install python deps
RUN python3 -m pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY . .

# Expose default Streamlit port
EXPOSE 8080

# Start Streamlit (bind to 0.0.0.0 so external platforms can route traffic)
CMD ["python3", "-m", "streamlit", "run", "app.py", "--server.port=8080", "--server.headless=true"]
