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
    # Mark every "pending"/"running" task left over from the previous
    # container as failed. Done here (not in TaskService.__init__) so it
    # runs exactly once per boot, regardless of how many gunicorn workers
    # we spawn or how often they recycle.
    echo "Cleaning up stale background tasks..."
    RUN_STALE_TASK_CLEANUP=1 python -c "from app.services.background_services.task_service import TaskService; TaskService()" \
      || echo "  (warning: stale-task cleanup failed, continuing)"

    echo "Starting Gunicorn (production)..."
    exec gunicorn -c gunicorn.conf.py "run:app"
else
    echo "Starting Werkzeug dev server..."
    exec python run.py
fi
