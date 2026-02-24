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

exec python run.py
