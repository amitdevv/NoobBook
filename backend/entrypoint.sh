#!/bin/bash
# Entrypoint for the NoobBook backend container.
#
# On first run the data/ volume is empty, so we seed it with the prompt
# configuration files that were staged during the Docker build.

set -e

# Copy default prompts into the volume if they are missing
if [ ! -f data/prompts/default_prompt.json ]; then
    echo "Seeding data/prompts/ from staging directory..."
    cp -r /app/_prompts_staging/* data/prompts/
fi

# Ensure other data directories exist inside the volume
mkdir -p data/projects data/tasks data/temp

exec python run.py
