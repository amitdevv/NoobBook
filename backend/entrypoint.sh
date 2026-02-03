#!/bin/bash
# Entrypoint for the NoobBook backend container.
#
# On first run the data/ volume is empty, so we seed it with the prompt
# configuration files that were staged during the Docker build.

set -e

# Ensure prompts directory exists inside the volume
mkdir -p data/prompts

# Sync prompt files from the baked-in staging directory into the volume.
# - Do NOT overwrite existing prompt files (users may customize them in the volume).
# - Copy any new prompt files that weren't present when the volume was first created.
echo "Syncing prompt files into data/prompts/ (non-destructive)..."
for f in /app/_prompts_staging/*; do
    base="$(basename "$f")"
    if [ ! -f "data/prompts/$base" ]; then
        cp "$f" "data/prompts/$base"
    fi
done

# Ensure other data directories exist inside the volume
mkdir -p data/projects data/tasks data/temp

exec python run.py
