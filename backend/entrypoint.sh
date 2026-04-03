#!/bin/bash
# Entrypoint for the NoobBook backend container.
#
# On first run the data/ volume is empty, so we seed it with the prompt
# configuration files that were staged during the Docker build.

set -e

# Ensure prompts directory exists inside the volume
mkdir -p data/prompts

# Sync prompt files from the baked-in staging directory into the volume.
# Always overwrite — prompt configs are part of the codebase, not user data.
echo "Syncing prompt files into data/prompts/..."
cp /app/_prompts_staging/* data/prompts/

# Ensure other data directories exist inside the volume
mkdir -p data/projects data/tasks data/temp

# Production: use Gunicorn (production WSGI server with gevent for concurrency)
# Development: use Werkzeug dev server (auto-reload, debug mode)
if [ "$FLASK_ENV" = "production" ]; then
    echo "Starting Gunicorn (production)..."
    exec gunicorn -c gunicorn.conf.py "run:app"
else
    echo "Starting Werkzeug dev server..."
    exec python run.py
fi
