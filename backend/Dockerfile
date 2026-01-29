FROM python:3.11-slim

# System dependencies for document processing and browser automation
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    ffmpeg \
    # Playwright Chromium dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser
RUN playwright install chromium

# Copy application code
COPY . .

# Stage prompt files so entrypoint can copy them into the mounted volume.
# The data/ volume mount would shadow the baked-in data/ directory, so we
# keep a pristine copy under /_prompts_staging/ to seed the volume on first run.
RUN cp -r data/prompts /app/_prompts_staging

# Create data directories (will be overlaid by volume mount)
RUN mkdir -p data/prompts data/projects data/tasks data/temp

# Make entrypoint executable
RUN chmod +x entrypoint.sh

EXPOSE 5001

ENTRYPOINT ["./entrypoint.sh"]
